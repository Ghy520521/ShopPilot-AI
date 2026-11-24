"""全局枚举：模型与 Schema 共用同一取值，避免魔法字符串散落。

兼容 Python 3.10+：用 (str, Enum) 替代 3.11 才引入的 StrEnum。
"""
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    SHIPPED = "shipped"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class TicketStatus(str, Enum):
    OPEN = "open"                # 待处理
    IN_PROGRESS = "in_progress"  # 处理中
    RESOLVED = "resolved"        # 已解决
    CLOSED = "closed"            # 已关闭


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
