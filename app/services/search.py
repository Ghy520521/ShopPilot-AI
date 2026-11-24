"""AI 自然语言工单检索。

链路：自然语言问题 -> LLM 输出受约束 SearchPlan ->
  (A) SQLAlchemy 白名单结构化过滤（状态/优先级/时间/订单号/关键词）
  (B) 向量语义召回相似历史工单 -> 合并去重 -> 分页返回。

安全红线：
- LLM 不接触数据库，只输出 SearchPlan（枚举 + 白名单字段 + 时间范围）；
- 后端用白名单字段显式构造查询，不拼接、不执行任何 LLM 提供的 SQL；
- 结构化过滤前先做权限过滤：普通用户只能检索自己创建的工单。
"""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embedding import cosine, get_embedding_provider
from app.core.enums import UserRole
from app.core.llm import get_llm_client
from app.models.order import Order
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import SearchPlan


def _apply_permission(stmt, user: User):
    """普通用户强制只能看自己创建的工单；管理员可见全部。"""
    if user.role != UserRole.ADMIN.value:
        return stmt.where(Ticket.creator_id == user.id)
    return stmt


def structured_search(db: Session, plan: SearchPlan, user: User) -> list[Ticket]:
    stmt = _apply_permission(select(Ticket), user)

    if plan.statuses:
        stmt = stmt.where(Ticket.status.in_(plan.statuses))
    if plan.priority:
        stmt = stmt.where(Ticket.priority == plan.priority)
    if plan.since:
        stmt = stmt.where(Ticket.created_at >= plan.since)
    if plan.until:
        stmt = stmt.where(Ticket.created_at <= plan.until)
    if plan.order_no:
        stmt = stmt.join(Order, Ticket.order_id == Order.id).where(
            Order.order_no == plan.order_no
        )

    base = list(db.scalars(stmt).all())

    # 关键词是“软召回”而不是硬过滤：命中了就按关键词收窄；
    # 没命中（规则解析噪声 / 说法与工单原文不一致）时回退到硬过滤候选，避免漏召回。
    if not plan.keywords:
        return base

    keyword_clauses = [
        or_(Ticket.title.ilike(f"%{kw}%"), Ticket.description.ilike(f"%{kw}%"))
        for kw in plan.keywords
    ]
    kw_hits = list(db.scalars(stmt.where(or_(*keyword_clauses))).all())
    return kw_hits or base


def semantic_search(db: Session, plan: SearchPlan, user: User) -> list[tuple[Ticket, float]]:
    provider = get_embedding_provider()
    query_vec = provider.embed(plan.semantic_query)
    stmt = _apply_permission(select(Ticket), user)
    scored: list[tuple[Ticket, float]] = []
    for ticket in db.scalars(stmt).all():
        score = cosine(query_vec, ticket.embedding or [])
        # 阈值过滤：只保留有实际语义重合的候选，避免零散共词被当相似工单召回
        # （本地哈希向量仅用于开发；生产换真实 embedding 后阈值按评测集重新标定）
        if score >= 0.25:
            scored.append((ticket, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[: settings.search_recall_k]


def nl_search(
    db: Session, user: User, question: str, page: int, page_size: int
) -> tuple[list[Ticket], int, SearchPlan, dict]:
    """返回 (当前页工单, 总命中数, 解析出的 SearchPlan, 调试计数)。"""
    plan = get_llm_client().parse_search_plan(question)

    structured = structured_search(db, plan, user)
    semantic = semantic_search(db, plan, user)
    semantic_ids = {t.id for t, _ in semantic}
    structured_ids = {t.id for t in structured}

    # 合并去重：结构化命中优先，语义召回补充；二者都没有的证据不交回大模型
    merged: list[Ticket] = list(structured)
    seen = structured_ids
    for ticket, _score in semantic:
        if ticket.id not in seen:
            merged.append(ticket)
            seen.add(ticket.id)

    total = len(merged)
    start = (page - 1) * page_size
    items = merged[start : start + page_size]

    debug = {
        "structured_count": len(structured),
        "semantic_count": len(semantic),
        "merged_count": total,
        "structured_ids": sorted(structured_ids),
        "semantic_ids": sorted(semantic_ids),
    }
    return items, total, plan, debug
