"""库存扣减。

两种并发控制思路：
1. 条件更新（默认，SQLite/PG 都可跑）：UPDATE ... SET stock = stock - q
   WHERE id = :pid AND stock >= :q，靠 rowcount 判断是否扣减成功，避免先查后扣的竞态。
2. 行级锁（PostgreSQL 生产）：事务内 SELECT ... FOR UPDATE 锁住商品行再扣减。
"""
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.product import Product


def deduct_stock(db: Session, product_id: int, quantity: int) -> bool:
    """条件更新扣减库存；库存不足返回 False，调用方回滚事务。"""
    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.stock >= quantity)
        .values(stock=Product.stock - quantity)
    )
    return result.rowcount == 1


def lock_product_row(db: Session, product_id: int) -> Product | None:
    """PostgreSQL 行级锁（FOR UPDATE）。SQLite 不支持，直接返回商品行。"""
    product = db.get(Product, product_id)
    if product is None:
        return None
    if db.bind.dialect.name == "postgresql":  # pragma: no cover - 需要 PG 验证
        db.execute(
            update(Product).where(Product.id == product_id).with_for_update()
        )
    return product
