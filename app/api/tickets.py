"""工单路由：生命周期管理 + AI 自然语言检索。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.enums import TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ticket import (
    NLSearchRequest,
    NLSearchResponse,
    TicketAssign,
    TicketCreate,
    TicketOut,
    TransitionRequest,
)
from app.services import ticket_service
from app.services.search import nl_search

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _ticket_to_out(t: Ticket) -> TicketOut:
    return TicketOut(
        id=t.id,
        public_no=t.public_no,
        title=t.title,
        description=t.description,
        status=t.status,
        priority=t.priority,
        order_id=t.order_id,
        creator_id=t.creator_id,
        assignee_id=t.assignee_id,
        created_at=t.created_at,
        logs=[
            {
                "from_status": log.from_status,
                "to_status": log.to_status,
                "operator_id": log.operator_id,
                "note": log.note,
                "created_at": log.created_at,
            }
            for log in t.logs
        ],
    )


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(req: TicketCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = ticket_service.create_ticket(db, user, req)
    return _ticket_to_out(ticket)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    status: TicketStatus | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if user.role != UserRole.ADMIN.value:
        stmt = stmt.where(Ticket.creator_id == user.id)
    if status:
        stmt = stmt.where(Ticket.status == status)
    if priority:
        stmt = stmt.where(Ticket.priority == priority)
    return [_ticket_to_out(t) for t in db.scalars(stmt).all()]


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="工单不存在")
    if ticket.creator_id != user.id and user.role != UserRole.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权查看该工单")
    return _ticket_to_out(ticket)


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign(
    ticket_id: int,
    req: TicketAssign,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="工单不存在")
    ticket_service.assign_ticket(db, ticket, req.assignee_id)
    return _ticket_to_out(ticket)


@router.post("/{ticket_id}/transition", response_model=TicketOut)
def transition(
    ticket_id: int,
    body: TransitionRequest,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="工单不存在")
    ticket = ticket_service.transition_ticket(db, ticket, body.to_status, operator, body.note)
    return _ticket_to_out(ticket)


@router.post("/search", response_model=NLSearchResponse)
def natural_language_search(
    req: NLSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total, plan, debug = nl_search(db, user, req.question, req.page, req.page_size)
    return NLSearchResponse(
        items=[_ticket_to_out(t) for t in items],
        total=total,
        debug={
            "plan": plan,
            "structured_count": debug["structured_count"],
            "semantic_count": debug["semantic_count"],
            "merged_count": debug["merged_count"],
        },
    )
