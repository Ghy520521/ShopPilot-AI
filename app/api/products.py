"""商品路由：公开浏览 + 管理员维护；热门商品走缓存，变更时主动失效。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import get_cache
from app.core.database import get_db
from app.core.deps import require_role
from app.core.enums import UserRole
from app.models.product import Category, Product
from app.schemas.common import Page
from app.schemas.product import (
    CategoryCreate,
    CategoryOut,
    ProductCreate,
    ProductOut,
)

router = APIRouter(prefix="/products", tags=["products"])

CACHE_PREFIX = "products:"
HOT_TTL = 60


def _to_out(p: Product) -> ProductOut:
    return ProductOut.model_validate(p)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return list(db.scalars(select(Category).order_by(Category.id)).all())


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    req: CategoryCreate,
    db: Session = Depends(get_db),
    _admin: UserRole = Depends(require_role(UserRole.ADMIN)),
):
    category = Category(name=req.name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("", response_model=Page[ProductOut])
def list_products(
    category_id: int | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
):
    cache = get_cache()
    keyword = (q or "").strip()
    cache_key = f"{CACHE_PREFIX}list:{category_id}:{keyword}:{page}:{page_size}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    stmt = select(Product).order_by(Product.id.desc())
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            Product.name.ilike(like)
            | Product.sku.ilike(like)
            | Product.description.ilike(like)
        )

    total = len(db.scalars(stmt).all())
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    result = Page[ProductOut](
        items=[_to_out(p) for p in items], total=total, page=page, page_size=page_size
    )
    cache.setex(cache_key, HOT_TTL, result.model_dump())
    return result


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return _to_out(product)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreate,
    db: Session = Depends(get_db),
    _admin: UserRole = Depends(require_role(UserRole.ADMIN)),
):
    if db.get(Category, req.category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="分类不存在")
    product = Product(
        name=req.name,
        description=req.description,
        sku=req.sku,
        price=req.price,
        stock=req.stock,
        category_id=req.category_id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    # 写操作后主动失效商品列表缓存，避免脏读
    get_cache().delete_prefix(CACHE_PREFIX)
    return _to_out(product)
