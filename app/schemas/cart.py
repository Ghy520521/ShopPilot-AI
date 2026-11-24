from pydantic import BaseModel, Field


class CartItemUpsert(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=999)


class CartItemOut(BaseModel):
    product_id: int
    product_name: str
    sku: str
    unit_price: float
    quantity: int
    subtotal: float

    model_config = {"from_attributes": True}
