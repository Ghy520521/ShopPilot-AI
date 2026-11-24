from pydantic import BaseModel, Field

from app.core.enums import OrderStatus


class OrderItemInput(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=999)


class OrderCreate(BaseModel):
    """下单请求。idempotency_key 由客户端生成（UUID），防止重试导致重复下单。"""

    idempotency_key: str = Field(min_length=8, max_length=128)
    use_cart: bool = True
    items: list[OrderItemInput] | None = None


class OrderItemOut(BaseModel):
    product_id: int
    product_name: str
    sku: str
    unit_price: float
    quantity: int
    subtotal: float

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: int
    order_no: str
    status: OrderStatus
    total_amount: float
    items: list[OrderItemOut]
    created_at: str

    model_config = {"from_attributes": True}
