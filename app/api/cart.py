"""购物车路由。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.order import CartItem
from app.models.product import Product
from app.models.user import User
from app.schemas.cart import CartItemOut, CartItemUpsert

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=list[CartItemOut])
def view_cart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.scalars(select(CartItem).where(CartItem.user_id == user.id)).all()
    result = []
    for ci in items:
        p = db.get(Product, ci.product_id)
        result.append(
            CartItemOut(
                product_id=p.id,
                product_name=p.name,
                sku=p.sku,
                unit_price=p.price,
                quantity=ci.quantity,
                subtotal=round(p.price * ci.quantity, 2),
            )
        )
    return result


@router.post("", response_model=list[CartItemOut], status_code=status.HTTP_200_OK)
def upsert_item(
    req: CartItemUpsert,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.get(Product, req.product_id)
    if product is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="商品不存在")
    cart_item = db.scalar(
        select(CartItem).where(
            CartItem.user_id == user.id, CartItem.product_id == req.product_id
        )
    )
    if cart_item:
        cart_item.quantity += req.quantity
    else:
        cart_item = CartItem(user_id=user.id, product_id=req.product_id, quantity=req.quantity)
        db.add(cart_item)
    db.commit()
    return view_cart(db, user)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cart_item = db.scalar(
        select(CartItem).where(
            CartItem.user_id == user.id, CartItem.product_id == product_id
        )
    )
    if cart_item:
        db.delete(cart_item)
        db.commit()
