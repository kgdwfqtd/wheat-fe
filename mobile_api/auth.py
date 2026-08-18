# -*- coding: utf-8 -*-
"""JWT 认证与密码加密"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from mobile_api.database import get_db, settings
from mobile_api.models import User

# JWT 配置
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_DAYS = settings.JWT_EXPIRE_DAYS

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """使用 bcrypt 加密密码"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码是否匹配"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建 JWT 访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire})
    # 确保 sub 是字符串（JWT 规范要求）
    if "sub" in to_encode and not isinstance(to_encode["sub"], str):
        to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    """验证 JWT 令牌并返回 payload"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI 依赖项：获取当前登录用户"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌无效或已过期",
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌缺少用户信息",
        )
    
    # sub 可能是字符串，需要转换为 int
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中的用户信息格式错误",
        )
    
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """可选认证：如果已登录则返回用户，否则返回 None"""
    if credentials is None:
        return None
    
    payload = verify_access_token(credentials.credentials)
    if payload is None:
        return None
    
    user_id = payload.get("sub")
    if user_id is None:
        return None
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None
    
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    return result.scalar_one_or_none()


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前用户为管理员"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


# 登录响应模型
from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    real_name: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    real_name: str
    role: str = "user"