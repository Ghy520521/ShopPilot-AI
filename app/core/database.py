"""SQLAlchemy 引擎、会话与声明式基类。

本地测试使用 SQLite；生产 / Docker 使用 PostgreSQL。两种方言共用同一套模型。
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        # SQLite 多线程访问需要关闭检查（FastAPI 线程池 + 测试）
        connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """创建全部表（开发期使用；生产请走 Alembic 迁移）。

    create_all 不会给已存在的表补列，这里对开发库做一次轻量补列：
    仅当列缺失时 ALTER TABLE ADD COLUMN，已存在则跳过。
    """
    # 触发模型注册
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    # (表名, 列名, 补列 SQL)
    columns = [
        ("products", "rating", "ALTER TABLE products ADD COLUMN rating FLOAT DEFAULT 0"),
        ("products", "sales", "ALTER TABLE products ADD COLUMN sales INTEGER DEFAULT 0"),
        ("products", "listed_at", "ALTER TABLE products ADD COLUMN listed_at DATETIME"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in columns:
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(ddl))
