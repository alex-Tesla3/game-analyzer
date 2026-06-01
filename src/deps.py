"""Shared FastAPI dependencies."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, Query, status
from jose import JWTError, jwt

from src.auth import ALGORITHM, SECRET_KEY, TokenData
from src.auth import UserInDB
from src.database import UserRepository
from src.api_limits import effective_api_quota, effective_plan_id
from auth import PLANS

SUPPORT_STAFF_ROLES = frozenset({"admin", "agent"})


def is_admin(user: UserInDB) -> bool:
    return user.role == "admin"


def is_support_staff(user: UserInDB) -> bool:
    return user.role in SUPPORT_STAFF_ROLES


def require_admin(user: UserInDB) -> None:
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以执行此操作")


def require_support_staff(user: UserInDB) -> None:
    if not is_support_staff(user):
        raise HTTPException(status_code=403, detail="权限不足")


async def get_current_user(token: Optional[str] = Query(None)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user_data = UserRepository.get_by_username(token_data.username)
    if user_data is None:
        raise credentials_exception

    plan_id = effective_plan_id(user_data)
    plan_defaults = PLANS.get(plan_id, PLANS["free"])

    return UserInDB(
        id=user_data["username"],
        username=user_data["username"],
        email=user_data.get("email", ""),
        full_name=user_data.get("full_name", ""),
        disabled=not bool(user_data.get("is_active", 1)),
        role=user_data.get("role", "user"),
        plan=plan_id,
        games_limit=int(user_data.get("games_limit") or plan_defaults.games_limit),
        api_quota=effective_api_quota(user_data),
        hashed_password=user_data.get("hashed_password", ""),
    )
