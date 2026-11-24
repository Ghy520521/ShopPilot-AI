"""工单：创建、分配、状态机流转与操作日志。"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.embedding import get_embedding_provider
from app.core.enums import TicketStatus
from app.models.ticket import Ticket, TicketLog
from app.models.user import User
from app.schemas.ticket import TicketCreate

# 合法状态流转表；CLOSED 为终态
TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS},
    TicketStatus.IN_PROGRESS: {TicketStatus.RESOLVED, TicketStatus.OPEN},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
    TicketStatus.CLOSED: set(),
}


def _build_public_no() -> str:
    return "TKT" + uuid.uuid4().hex[:10].upper()


def create_ticket(db: Session, creator: User, req: TicketCreate) -> Ticket:
    provider = get_embedding_provider()
    text = f"{req.title} {req.description}"
    ticket = Ticket(
        public_no=_build_public_no(),
        title=req.title,
        description=req.description,
        priority=req.priority,
        order_id=req.order_id,
        creator_id=creator.id,
        embedding=provider.embed(text),
    )
    db.add(ticket)
    db.add(
        TicketLog(
            ticket=ticket,
            from_status=None,
            to_status=TicketStatus.OPEN,
            operator_id=creator.id,
            note="工单创建",
        )
    )
    db.commit()
    db.refresh(ticket)
    return ticket


def assign_ticket(db: Session, ticket: Ticket, assignee_id: int) -> Ticket:
    if db.get(User, assignee_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="被指派人不存在")
    ticket.assignee_id = assignee_id
    db.commit()
    db.refresh(ticket)
    return ticket


def transition_ticket(
    db: Session, ticket: Ticket, to_status: TicketStatus, operator: User, note: str | None = None
) -> Ticket:
    current = TicketStatus(ticket.status)
    allowed = TRANSITIONS.get(current, set())
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"不允许从 {current.value} 流转到 {to_status.value}",
        )
    ticket.status = to_status.value
    db.add(
        TicketLog(
            ticket_id=ticket.id,
            from_status=current.value,
            to_status=to_status.value,
            operator_id=operator.id,
            note=note,
        )
    )
    db.commit()
    db.refresh(ticket)
    return ticket
