"""工单 Schema，以及 AI 自然语言检索的受约束查询计划 SearchPlan。

关键安全约束：LLM 只允许输出 SearchPlan（枚举 / 白名单字段 / 时间范围），
后端据此用 SQLAlchemy 构造查询，绝不执行 LLM 生成的原始 SQL。
"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    order_id: int | None = None
    title: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1)
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketAssign(BaseModel):
    assignee_id: int


class TicketLogOut(BaseModel):
    from_status: TicketStatus | None
    to_status: TicketStatus
    operator_id: int
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: int
    public_no: str
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    order_id: int | None
    creator_id: int
    assignee_id: int | None
    created_at: datetime
    logs: list[TicketLogOut] = []

    model_config = {"from_attributes": True}


class TransitionRequest(BaseModel):
    to_status: TicketStatus
    note: str | None = None


# ---------- AI 自然语言检索 ----------

class SearchPlan(BaseModel):
    """LLM 允许输出的全部内容：枚举、白名单字段、时间范围、关键词、语义查询串。"""

    statuses: list[TicketStatus] | None = Field(
        default=None, description="允许的工单状态枚举列表，禁止其他取值"
    )
    priority: TicketPriority | None = None
    since: datetime | None = Field(default=None, description="起始时间（含）")
    until: datetime | None = Field(default=None, description="截止时间（含）")
    keywords: list[str] = Field(default_factory=list, description="精确关键词（标题/描述/订单号）")
    order_no: str | None = Field(default=None, description="明确提到的订单号，用于 SQL 精确匹配")
    semantic_query: str = Field(default="", description="用于向量语义召回的自然语言串")


class NLSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)


class NLSearchDebug(BaseModel):
    plan: SearchPlan
    structured_count: int
    semantic_count: int
    merged_count: int


class NLSearchResponse(BaseModel):
    items: list[TicketOut]
    total: int
    debug: NLSearchDebug | None = None
