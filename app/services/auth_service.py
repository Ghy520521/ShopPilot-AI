"""注册 / 登录业务逻辑。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.core.security import hash_password, verify_password
from app.models.user import User


class AuthError(Exception):
    pass


def register(db: Session, username: str, email: str, password: str) -> User:
    exists = db.scalar(select(User).where((User.username == username) | (User.email == email)))
    if exists:
        raise AuthError("用户名或邮箱已被注册")
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user and verify_password(password, user.password_hash):
        return user
    return None
