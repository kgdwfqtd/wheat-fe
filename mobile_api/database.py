# -*- coding: utf-8 -*-
"""数据库引擎与会话管理"""
import os
from typing import AsyncGenerator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase


# .env 文件路径（在 mobile_api 目录下）
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


class Settings(BaseSettings):
    """从 .env 加载配置"""
    # PostgreSQL 配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "wheat_fe"
    
    # JWT 配置
    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 7
    
    # 服务器配置
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8001
    
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


settings = Settings()

# 安全提示：生产环境必须通过环境变量或 .env 文件设置 `JWT_SECRET_KEY`
if not settings.JWT_SECRET_KEY:
    import warnings
    warnings.warn(
        "JWT_SECRET_KEY 未设置；请在生产环境通过环境变量或 .env 配置该值以确保安全。",
        UserWarning,
    )

# PostgreSQL 连接 URL（SQLAlchemy asyncpg 驱动）
DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

# 创建异步引擎
# 添加 connect_args 设置客户端编码为 UTF8
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    future=True,
    connect_args={
        "server_settings": {
            "client_encoding": "UTF8",
        }
    }
)

# 创建异步会话工厂
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库表结构（用于启动脚本）"""
    from mobile_api.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表结构初始化完成")


async def drop_db():
    """删除所有表结构（谨慎使用）"""
    from mobile_api.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("⚠️ 所有表已删除")