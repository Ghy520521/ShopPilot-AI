"""下单与订单查询：事务一致性、条件扣库存、幂等键。"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import OrderStatus
from app.models.order import CartItem, Order, OrderItem
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate
from app.services import inventory


class OrderError(Exception):
    pass


def _build_order_no() -> str:
    return "ORD" + uuid.uuid4().hex[:12].upper()


def create_order(db: Session, user: User, req: OrderCreate) -> Order:
    # 1) 幂等：同一用户 + 同一幂等键重复请求，直接返回首次订单，不重复扣库存
    existing = db.scalar(
        select(Order).where(
            Order.idempotency_key == req.idempotency_key,
            Order.user_id == user.id,
        )
    )
    if existing:
        return existing

    # 2) 汇总待购商品：来自购物车或直接传入
    lines: list[tuple[Product, int]] = []
    if req.use_cart:
        cart_items = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all()
        if not cart_items:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="购物车为空")
        for ci in cart_items:
            product = db.get(Product, ci.product_id)
            if product is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="购物车中存在失效商品")
            lines.append((product, ci.quantity))
    else:
        if not req.items:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="未提供下单商品")
        for item in req.items:
            product = db.get(Product, item.product_id)
            if product is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"商品 {item.product_id} 不存在")
            lines.append((product, item.quantity))

    # 3) 事务内：条件扣减库存 -> 写订单与订单快照 -> 清购物车；任一失败整体回滚
    try:
        for product, qty in lines:
            if not inventory.deduct_stock(db, product.id, qty):
                raise OrderError(f"商品 {product.sku} 库存不足，下单失败")

        total = round(sum(p.price * qty for p, qty in lines), 2)
        order = Order(
            order_no=_build_order_no(),
            user_id=user.id,
            status=OrderStatus.PENDING_PAYMENT,
            total_amount=total,
            idempotency_key=req.idempotency_key,
        )
        db.add(order)
        db.flush()

        for product, qty in lines:
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    sku=product.sku,
                    unit_price=product.price,
                    quantity=qty,
                    subtotal=round(product.price * qty, 2),
                )
            )

        if req.use_cart:
            for ci in db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all():
                db.delete(ci)

        db.commit()
        db.refresh(order)
        return order
    except OrderError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def list_orders(db: Session, user: User) -> list[Order]:
    stmt = select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    return list(db.scalars(stmt).all())


def get_order(db: Session, user: User, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if order.user_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="无权查看该订单")
    return order
