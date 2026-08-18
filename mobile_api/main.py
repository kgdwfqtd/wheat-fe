# -*- coding: utf-8 -*-
"""FastAPI 主入口 — 移动端数据采集 API"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from mobile_api.database import engine, get_db, settings, AsyncSessionLocal
from mobile_api.models import (
    User, Plot, SoilData, Phenology, Emergence,
    AgronomicTraits, Physiological, YieldData, QualityData, OperationLog,
    AuditLog, ExperimentBase,
)
from mobile_api.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_user_optional, require_admin,
    TokenResponse, LoginRequest, RegisterRequest,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时执行"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(User).limit(1))
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"⚠️ 数据库连接失败: {e}")
    
    yield
    
    await engine.dispose()
    print("🔌 数据库连接已释放")


app = FastAPI(
    title="纳米铁肥小麦试验 — 移动端数据采集 API",
    description="田间数据采集后端服务",
    version="0.2.0",
    lifespan=lifespan,
)

import os

# CORS origins 可以通过环境变量 `MOBILE_API_CORS_ORIGINS` 配置，逗号分隔。
cors_env = os.getenv("MOBILE_API_CORS_ORIGINS", "")
if cors_env:
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    allow_origins = ["*"]
    if os.getenv("ENV", "development") == "production":
        import warnings
        warnings.warn("生产环境中未配置 MOBILE_API_CORS_ORIGINS，当前允许所有来源（'*'），请设置以限制来源。")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ============================================================
# 健康检查
# ============================================================
@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(User).limit(1))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return {
        "status": "ok",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.2.0",
    }


@app.get("/api/v1/config")
async def get_config():
    return {
        "app_name": "纳米铁肥小麦试验数据采集",
        "version": "0.2.0",
        "tables": {
            "soil": "土壤数据",
            "phenology": "物候期",
            "emergence": "出苗调查",
            "agronomic": "农艺性状",
            "physiological": "生理指标",
            "yield": "产量数据",
            "quality": "品质数据",
            "operation": "操作日志",
        },
    }


# ============================================================
# 认证 API
# ============================================================
@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )
    
    access_token = create_access_token(
        data={"sub": user.id, "role": user.role, "username": user.username}
    )
    
    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        real_name=user.real_name,
        role=user.role,
    )


@app.post("/api/v1/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用",
        )

    # 安全修复：注册接口不允许选择管理员角色，只能注册普通用户
    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        real_name=request.real_name,
        role="user",  # 强制限制为 user，防止提权
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(
        data={"sub": user.id, "role": user.role, "username": user.username}
    )

    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        username=user.username,
        real_name=user.real_name,
        role=user.role,
    )


@app.get("/api/v1/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "real_name": current_user.real_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


# ============================================================
# 小区 API
# ============================================================
@app.get("/api/v1/bases")
async def list_bases(
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExperimentBase).order_by(ExperimentBase.created_at.desc()))
    bases = result.scalars().all()
    return [{
        "id": b.id,
        "base_code": b.base_code,
        "base_name": b.base_name,
        "admin_code": b.admin_code,
        "remarks": b.remarks,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    } for b in bases]


@app.get("/api/v1/bases/{base_code}")
async def get_base_detail(
    base_code: str,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ExperimentBase).where(ExperimentBase.base_code == base_code))
    base = result.scalar_one_or_none()
    if base is None:
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")
    return {
        "id": base.id,
        "base_code": base.base_code,
        "base_name": base.base_name,
        "admin_code": base.admin_code,
        "remarks": base.remarks,
        "created_at": base.created_at.isoformat() if base.created_at else None,
    }


@app.get("/api/v1/plots")
async def list_plots(
    base_code: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Plot)
    if base_code:
        query = query.where(Plot.base_code == base_code)
    query = query.order_by(Plot.block, Plot.treatment)
    result = await db.execute(query)
    plots = result.scalars().all()
    return [
        {
            "id": p.id,
            "base_code": p.base_code,
            "plot_code": p.plot_code,
            "block": p.block,
            "treatment": p.treatment,
            "area_m2": p.area_m2,
        }
        for p in plots
    ]




@app.get("/api/v1/plots/by-id/{plot_id}")
async def get_plot_by_id(
    plot_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Plot).where(Plot.id == plot_id)
    )
    plot = result.scalar_one_or_none()
    if plot is None:
        raise HTTPException(status_code=404, detail=f"小区 ID {plot_id} 不存在")
    return {
        "id": plot.id,
        "plot_code": plot.plot_code,
        "block": plot.block,
        "treatment": plot.treatment,
        "treatment_name": plot.treatment,
        "area_m2": plot.area_m2,
        "field_name": plot.field_name,
    }


@app.get("/api/v1/data-query/{table}")
async def query_data_by_plot_id(
    table: str,
    plot_id: int,
    base_code: str | None = None,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if table not in VALID_TABLES:
        raise HTTPException(status_code=400, detail="非法的表名")
    model = VALID_TABLES[table]
    plot_result = await db.execute(select(Plot).where(Plot.id == plot_id))
    plot = plot_result.scalar_one_or_none()
    if plot is None:
        return []
    query = select(model).where(model.plot_id == plot_id)
    if base_code:
        query = query.where(model.base_code == base_code)
    if table == "soil":
        query = query.order_by(model.phase)
    result = await db.execute(query)
    records = result.scalars().all()
    return [
        {col.name: getattr(r, col.name) for col in model.__table__.columns}
        for r in records
    ]
@app.get("/api/v1/plots/{plot_code}")
async def get_plot(
    plot_code: str,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Plot).where(Plot.plot_code == plot_code)
    )
    plot = result.scalar_one_or_none()
    if plot is None:
        raise HTTPException(status_code=404, detail=f"小区 {plot_code} 不存在")
    return {
        "id": plot.id,
        "plot_code": plot.plot_code,
        "block": plot.block,
        "treatment": plot.treatment,
        "area_m2": plot.area_m2,
        "field_name": plot.field_name,
    }


# ============================================================
# 数据录入 API
# ============================================================
VALID_TABLES = {
    "soil": SoilData,
    "phenology": Phenology,
    "emergence": Emergence,
    "agronomic": AgronomicTraits,
    "physiological": Physiological,
    "yield": YieldData,
    "quality": QualityData,
}


@app.post("/api/v1/data/{table}")
async def submit_data(
    table: str,
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if table not in VALID_TABLES:
        raise HTTPException(status_code=400, detail=f"非法的表名: {table}")

    model = VALID_TABLES[table]
    plot_id = data.get("plot_id")
    if plot_id is None:
        raise HTTPException(status_code=400, detail="缺少 plot_id 字段")

    # 验证小区存在
    plot_result = await db.execute(select(Plot).where(Plot.id == plot_id))
    if plot_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"小区 {plot_id} 不存在")

    # 查找已有记录（upsert 逻辑）
    if table == "soil":
        phase = data.get("phase", "播前")
        existing = await db.execute(
            select(SoilData).where(SoilData.plot_id == plot_id, SoilData.phase == phase)
        )
        record = existing.scalar_one_or_none()
    else:
        existing = await db.execute(
            select(model).where(model.plot_id == plot_id)
        )
        record = existing.scalar_one_or_none()

    # 过滤 None 值
    clean_data = {k: v for k, v in data.items() if v is not None}

    action = "created"
    if record:
        # 更新已有记录
        action = "updated"
        for key, value in clean_data.items():
            if hasattr(record, key):
                setattr(record, key, value)
    else:
        # 创建新记录
        record = model(**clean_data)
        db.add(record)
        action = "created"

    await db.commit()
    await db.refresh(record)

    # 显式写入审计日志（替代 AsyncSession 事件，确保在异步环境下正常工作）
    try:
        from mobile_api.models import AuditLog
        from sqlalchemy import insert as sa_insert
        import json as _json
        
        # 记录新值
        new_values = {}
        for col in model.__table__.columns:
            val = getattr(record, col.name, None)
            if val is not None and col.name != 'id':
                # 序列化日期等复杂类型
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                new_values[col.name] = val
        
        audit_entry = {
            "user_id": current_user.id,
            "table_name": model.__tablename__,
            "record_id": record.id,
            "action": "UPDATE" if action == "updated" else "INSERT",
            "old_values": None if action == "created" else {},
            "new_values": new_values,
        }
        
        # 使用同步连接写入审计日志（避免异步会话事件问题）
        from mobile_api.database import engine
        async with engine.begin() as conn:
            await conn.execute(
                sa_insert(AuditLog.__table__).values(**audit_entry)
            )
    except Exception as e:
        logger.warning(f"Failed to write audit log: {e}")

    return {
        "status": "ok",
        "action": action,
        "record_id": record.id,
        "table": table,
        "plot_id": plot_id,
        "operator": current_user.real_name,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/data/{table}/{plot_code}")
async def get_data(
    table: str,
    plot_code: str,
    base_code: str | None = None,
    current_user: User = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    if table not in VALID_TABLES:
        raise HTTPException(status_code=400, detail=f"非法的表名: {table}")
    
    model = VALID_TABLES[table]
    
    plot_result = await db.execute(
        select(Plot).where(Plot.plot_code == plot_code)
    )
    plot = plot_result.scalar_one_or_none()
    if plot is None:
        raise HTTPException(status_code=404, detail=f"小区 {plot_code} 不存在")
    
    query = select(model).where(model.plot_id == plot.id)
    if base_code:
        query = query.where(model.base_code == base_code)
    if table == "soil":
        query = query.order_by(model.phase)
        result = await db.execute(query)
        records = result.scalars().all()
        return [
            {col.name: getattr(r, col.name) for col in model.__table__.columns}
            for r in records
        ]
    else:
        result = await db.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return {col.name: getattr(record, col.name) for col in model.__table__.columns}


# ============================================================
# 操作日志 API
# ============================================================
@app.post("/api/v1/operations")
async def create_operation(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db._audit_user_id = current_user.id
    
    operation = OperationLog(
        plot_id=data.get("plot_id"),
        date=data.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
        time=data.get("time", ""),
        op_type=data.get("op_type", ""),
        treatment=data.get("treatment", ""),
        block=data.get("block", ""),
        dosage=data.get("dosage", ""),
        weather=data.get("weather", ""),
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        operator=current_user.real_name,
        remarks=data.get("remarks", ""),
    )
    db.add(operation)
    await db.commit()
    await db.refresh(operation)
    
    return {
        "status": "ok",
        "operation_id": operation.id,
        "operator": current_user.real_name,
    }


# ============================================================
# 管理 API
# ============================================================
@app.get("/api/v1/audit-logs")
async def list_audit_logs(
    table: str = None,
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if table:
        query = query.where(AuditLog.table_name == table)
    query = query.limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "table_name": l.table_name,
            "record_id": l.record_id,
            "action": l.action,
            "old_values": l.old_values,
            "new_values": l.new_values,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]


@app.get("/api/v1/users")
async def list_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(User.id)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "real_name": u.real_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]