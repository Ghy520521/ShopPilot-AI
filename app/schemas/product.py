from datetime import datetime

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class ProductOut(BaseModel):
    id: int
    name: str
    description: str | None
    sku: str
    price: float
    stock: int
    rating: float = 0.0
    sales: int = 0
    listed_at: datetime | None = None
    category_id: int
    category: CategoryOut | None = None

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    sku: str = Field(min_length=1, max_length=64)
    price: float = Field(gt=0)
    stock: int = Field(ge=0)
    category_id: int
