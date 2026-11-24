"""pytest 公共夹具：内存 SQLite + 依赖覆盖，无需 Postgres / Redis / 外部 LLM。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User


@pytest.fixture(scope="session")
def _engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import app.models  # noqa: F401  注册全部模型

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(_engine):
    # 每个测试重建全部表，避免服务内 rollback 清掉夹具造数
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    session = sessionmaker(bind=_engine)()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------- 通用造数助手 ----------

def _make_user(db, username: str, role: str = "user", email: str | None = None) -> User:
    user = User(
        username=username,
        email=email or f"{username}@example.com",
        password_hash=hash_password("password123"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(client, db_session):
    _make_user(db_session, "admin", role="admin")
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
    return resp.json()["access_token"]


def register_and_login(client, username: str) -> str:
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "password123"},
    )
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": "password123"}
    )
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
