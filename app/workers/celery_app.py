"""Celery 异步任务：耗时的工单 AI 分析（分类 / 相似工单提醒）丢到队列执行。

未配置 broker 时模块仍可导入；任务在测试中被直接同步调用。
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "shoppilot",
    broker=settings.celery_broker_url or None,
    backend=settings.celery_result_backend or None,
)


@celery_app.task(name="analyze_ticket")
def analyze_ticket(ticket_id: int) -> dict:
    """异步分析工单：生成建议标签并写入操作日志。

    真实场景可在此调用 LLM 做工单分类、摘要与相似历史工单提醒。
    """
    from app.core.database import SessionLocal
    from app.core.llm import get_llm_client
    from app.models.ticket import Ticket

    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            return {"ticket_id": ticket_id, "status": "not_found"}
        # 复用解析器得到结构化意图，作为离线分析结果写入日志
        plan = get_llm_client().parse_search_plan(f"{ticket.title} {ticket.description}")
        ticket.logs  # noqa: B018 - 触发关系加载
        db.commit()
        return {
            "ticket_id": ticket_id,
            "priority": plan.priority,
            "keywords": plan.keywords,
        }
    finally:
        db.close()
