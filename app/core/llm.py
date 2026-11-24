"""LLM 适配层。

职责边界（重要）：LLM 只负责把自然语言解析成受约束的 SearchPlan，
永远不接触数据库连接、不生成 SQL、不执行任何语句。
生产环境把 get_llm_client() 换成真实大模型的结构化输出（function calling / JSON mode）。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Protocol

from app.core.config import settings
from app.core.enums import TicketPriority, TicketStatus
from app.schemas.ticket import SearchPlan


class LLMClient(Protocol):
    def parse_search_plan(self, question: str) -> SearchPlan: ...


class RuleBasedParser:
    """开发 / 测试用的确定性解析器：从中英文问句中抽取枚举、时间与关键词。"""

    def parse_search_plan(self, question: str) -> SearchPlan:
        q = question.strip()
        statuses: list[TicketStatus] | None = None
        ql = q.lower()

        unresolved_words = ["未解决", "未处理", "待处理", "还没解决", "还没有解决", "没有解决", "尚未处理", "没解决", "尚未处理完成"]
        if any(w in q for w in unresolved_words) or any(
            w in ql for w in ["unresolved", "open tickets", "not solved"]
        ):
            statuses = [TicketStatus.OPEN, TicketStatus.IN_PROGRESS]
        elif "已关闭" in q or "closed" in ql:
            statuses = [TicketStatus.CLOSED]
        elif "解决" in q or "resolved" in ql:
            # “解决的高优先级工单”按已解决理解（未解决已在上面拦截）
            statuses = [TicketStatus.RESOLVED]
        elif "处理中" in q or "in progress" in ql:
            statuses = [TicketStatus.IN_PROGRESS]

        priority: TicketPriority | None = None
        if any(w in q for w in ["高优先级", "紧急", "高优先"]) or "high" in ql:
            priority = TicketPriority.HIGH
        elif "低优先级" in q or "low" in ql:
            priority = TicketPriority.LOW
        elif "中优先级" in q or "medium" in ql:
            priority = TicketPriority.MEDIUM

        since: datetime | None = None
        m = re.search(r"最近?\s*(\d+)\s*天", q)
        if m:
            since = datetime.now(timezone.utc) - timedelta(days=int(m.group(1)))
        elif "最近一周" in q or "过去7天" in q:
            since = datetime.now(timezone.utc) - timedelta(days=7)
        elif "最近一个月" in q or "过去30天" in q:
            since = datetime.now(timezone.utc) - timedelta(days=30)

        order_no: str | None = None
        m = re.search(r"(ORD[-_]?[A-Z0-9]+)", q, flags=re.IGNORECASE)
        if m:
            order_no = m.group(1).upper()

        # 关键词：去掉状态 / 优先级 / 时间等抽取词后的剩余实词，供 SQL 精确匹配
        keywords = self._extract_keywords(q)

        return SearchPlan(
            statuses=statuses,
            priority=priority,
            since=since,
            until=None,
            keywords=keywords,
            order_no=order_no,
            semantic_query=q,
        )

    @staticmethod
    def _extract_keywords(q: str) -> list[str]:
        """先剔除状态 / 优先级 / 时间 / 语气短语，再从剩余实词里取关键词。

        避免把“高优/先级/级物/解决”这类碎片当成检索词，导致硬过滤漏召回。
        """
        from app.core.embedding import tokenize

        # 先按正则吃掉时间表达
        remain = re.sub(r"最近?\s*\d+\s*天", " ", q)
        remain = re.sub(r"过去\d+天|最近一周|最近一个月|过去30天", " ", remain)
        # 再按词表剔除语气 / 状态 / 优先级 / 通用词
        phrases = [
            "查一下", "查找", "找出", "有没有", "所有", "一下", "最近", "提到",
            "高优先级", "低优先级", "中优先级", "紧急",
            "未解决", "还没解决", "还没有解决", "没有解决", "尚未处理完成",
            "尚未处理", "没解决", "已解决", "解决", "已关闭", "处理中",
            "工单", "案例", "问题", "情况", "但", "完成",
        ]
        for p in phrases:
            remain = remain.replace(p, " ")

        stop = {
            "最近", "天", "高优先级", "紧急", "未解决", "已解决",
            "已关闭", "处理中", "查一下", "物流工单",
        }
        fragment_chars = set("查一下最近天还没的了吗呢吧但、，。")
        words = [
            w for w in tokenize(remain)
            if w not in stop and len(w) >= 2 and not any(c in fragment_chars for c in w)
        ]
        # 去重保序
        seen, result = set(), []
        for w in words:
            if w not in seen:
                seen.add(w)
                result.append(w)
        return result[:5]


class OpenAIStructuredClient:
    """生产占位：通过结构化输出让模型返回 SearchPlan（function calling / JSON mode）。

    必须显式配置 LLM_API_KEY 才启用；未配置时 get_llm_client() 不会选中它。
    """

    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY 未配置，无法使用 OpenAIStructuredClient")

    def parse_search_plan(self, question: str) -> SearchPlan:  # pragma: no cover
        # 真实实现：调用 chat.completions，response_format=SearchPlan，
        # 服务端仍需用 SearchPlan.model_validate 二次校验，非法枚举直接拒绝。
        raise NotImplementedError("接入真实 LLM 后在此实现结构化输出调用")


def get_llm_client() -> LLMClient:
    if settings.llm_provider != "mock" and settings.llm_api_key:
        return OpenAIStructuredClient()  # type: ignore[return-value]
    return RuleBasedParser()
