"""订单路由：下单（幂等）、订单列表与详情。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.order import Order
from app.models.user import User
from app.schemas.order import OrderCreate, OrderOut, OrderItemOut
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_no=order.order_no,
        status=order.status,
        total_amount=order.total_amount,
        items=[
            OrderItemOut(
                product_id=it.product_id,
                product_name=it.product_name,
                sku=it.sku,
                unit_price=it.unit_price,
                quantity=it.quantity,
                subtotal=it.subtotal,
            )
            for it in order.items
        ],
        created_at=order.created_at.isoformat(),
    )


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    req: OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = order_service.create_order(db, user, req)
    return _order_to_out(order)


@router.get("", response_model=list[OrderOut])
def list_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [_order_to_out(o) for o in order_service.list_orders(db, user)]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    order = order_service.get_order(db, user, order_id)
    return _order_to_out(order)
