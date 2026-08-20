# -*- coding: utf-8 -*-
"""SQLAlchemy 模型定义 — 完整映射业务表 + users + audit_log"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    UniqueConstraint, CheckConstraint, ForeignKey, Index, JSON,
    event,
)
from sqlalchemy.orm import Session
from mobile_api.database import Base


# ============================================================
# 用户认证表
# ============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="ck_users_role"),
    )


# ============================================================
# 审计日志表
# ============================================================
class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    table_name = Column(String(50), nullable=False, index=True)
    record_id = Column(Integer, nullable=False, index=True)
    action = Column(String(10), nullable=False)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("action IN ('INSERT', 'UPDATE', 'DELETE')", name="ck_audit_log_action"),
        Index("ix_audit_log_table_record", "table_name", "record_id"),
    )


# ============================================================
# 业务数据表
# ============================================================
class ExperimentBase(Base):
    __tablename__ = "experiment_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    base_code = Column(String(30), unique=True, nullable=False, index=True)
    base_name = Column(String(200), nullable=False)
    admin_code = Column(String(20), default="")
    remarks = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Plot(Base):
    __tablename__ = "plots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    block = Column(String(10), nullable=False)
    treatment = Column(String(20), nullable=False)
    plot_code = Column(String(20), unique=True, nullable=False)
    area_m2 = Column(Float, default=20.0)
    field_name = Column(String(100), default="")

    __table_args__ = (
        UniqueConstraint("base_code", "block", "treatment", name="uq_plots_base_block_treatment"),
    )


class SoilData(Base):
    __tablename__ = "soil_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    phase = Column(String(10), nullable=False)
    ph = Column(Float)
    fe_available = Column(Float)
    fe_total = Column(Float)
    organic_matter = Column(Float)
    p_available = Column(Float)
    k_available = Column(Float)
    cec = Column(Float)
    bulk_density = Column(Float)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")

    __table_args__ = (
        UniqueConstraint("plot_id", "phase", name="uq_soil_data_plot_phase"),
        CheckConstraint("phase IN ('播前', '收获后')", name="ck_soil_data_phase"),
    )


class Phenology(Base):
    __tablename__ = "phenology"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, unique=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    sowing = Column(String(20))
    emergence = Column(String(20))
    tillering = Column(String(20))
    overwinter = Column(String(20))
    regreening = Column(String(20))
    jointing = Column(String(20))
    heading = Column(String(20))
    flowering = Column(String(20))
    filling = Column(String(20))
    maturity = Column(String(20))
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


class Emergence(Base):
    __tablename__ = "emergence"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, unique=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    seeds_sown = Column(Integer)
    emerged_7d = Column(Integer)
    rate_7d = Column(Float)
    emerged_14d = Column(Integer)
    rate_14d = Column(Float)
    basic_seedlings = Column(Float)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


class AgronomicTraits(Base):
    __tablename__ = "agronomic_traits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, unique=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    tillers_prewinter = Column(Float)
    tillers_postregreen = Column(Float)
    tillers_jointing = Column(Float)
    plant_height = Column(Float)
    lai_jointing = Column(Float)
    lai_heading = Column(Float)
    dry_weight_jointing = Column(Float)
    dry_weight_heading = Column(Float)
    dry_weight_maturity = Column(Float)
    root_dry_weight = Column(Float)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


class Physiological(Base):
    __tablename__ = "physiological"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, unique=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    spad_jointing = Column(Float)
    spad_heading = Column(Float)
    spad_filling = Column(Float)
    photo_rate_heading = Column(Float)
    photo_rate_filling = Column(Float)
    active_fe_jointing = Column(Float)
    active_fe_filling = Column(Float)
    cat = Column(Float)
    pod = Column(Float)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


class YieldData(Base):
    __tablename__ = "yield_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, unique=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    spikes_per_mu = Column(Float)
    grains_per_spike = Column(Float)
    thousand_grain_wt_1 = Column(Float)
    thousand_grain_wt_2 = Column(Float)
    theoretical_yield = Column(Float)
    actual_yield = Column(Float)
    harvest_index = Column(Float)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


class QualityData(Base):
    __tablename__ = "quality_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="CASCADE"), nullable=False, unique=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    grain_protein = Column(Float)
    wet_gluten = Column(Float)
    sds_sedimentation = Column(Float)
    grain_fe = Column(Float)
    flour_fe = Column(Float)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


class OperationLog(Base):
    __tablename__ = "operation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plot_id = Column(Integer, ForeignKey("plots.id", ondelete="SET NULL"), nullable=True)
    base_code = Column(String(30), nullable=False, default="000000000000", index=True)
    date = Column(String(20), nullable=False)
    time = Column(String(10))
    op_type = Column(String(50), nullable=False)
    treatment = Column(String(20))
    block = Column(String(10))
    dosage = Column(String(200))
    weather = Column(String(20))
    temperature = Column(Float)
    humidity = Column(Float)
    operator = Column(String(50))
    remarks = Column(Text)
    created_by = Column(String(50), default="")
    updated_by = Column(String(50), default="")


# ============================================================
# 审计日志自动记录
# - before_flush: 收集快照
# - after_flush: 用原生 SQL 写入审计日志（避免 ORM 递归）
# ============================================================
BUSINESS_TABLES = (
    SoilData, Phenology, Emergence, AgronomicTraits,
    Physiological, YieldData, QualityData, OperationLog,
)


def _is_business(instance):
    return isinstance(instance, BUSINESS_TABLES)


@event.listens_for(Session, "before_flush")
def capture_snapshots(session, flush_context, instances):
    """flush 前：记录实例旧值快照"""
    if getattr(session, "_audit_processing", False):
        return

    session._audit_snapshots = {}
    for instance in list(session.new) + list(session.dirty) + list(session.deleted):
        if not _is_business(instance):
            continue
        if instance.id is not None:
            session._audit_snapshots[id(instance)] = {
                "table": instance.__tablename__,
                "old": _row_to_dict(instance),
            }


@event.listens_for(Session, "after_flush")
def write_audit_logs(session, flush_context):
    """flush 后：用原生 SQL 写入审计日志"""
    if getattr(session, "_audit_processing", False):
        return

    snapshots = getattr(session, "_audit_snapshots", {})
    entries = []

    for instance in session.new:
        if not _is_business(instance):
            continue
        entries.append((
            getattr(session, "_audit_user_id", None),
            instance.__tablename__,
            instance.id or 0,
            "INSERT",
            None,
            _row_to_dict(instance),
        ))

    for instance in session.dirty:
        if not _is_business(instance):
            continue
        snap = snapshots.get(id(instance), {})
        entries.append((
            getattr(session, "_audit_user_id", None),
            instance.__tablename__,
            instance.id,
            "UPDATE",
            snap.get("old"),
            _row_to_dict(instance),
        ))

    for instance in session.deleted:
        if not _is_business(instance):
            continue
        snap = snapshots.get(id(instance), {})
        entries.append((
            getattr(session, "_audit_user_id", None),
            instance.__tablename__,
            instance.id,
            "DELETE",
            snap.get("old"),
            None,
        ))

    if not entries:
        return

    # 使用 SQLAlchemy Core 的 insert() 表达式，安全绑定参数
    from sqlalchemy import insert as sa_insert
    import json as _json

    values_list = []
    for uid, tbl, rid, act, old, new in entries:
        values_list.append({
            "user_id": uid,
            "table_name": tbl,
            "record_id": rid,
            "action": act,
            "old_values": _json.dumps(old, ensure_ascii=False) if old else None,
            "new_values": _json.dumps(new, ensure_ascii=False) if new else None,
        })

    stmt = sa_insert(AuditLog.__table__).values(values_list)
    session.execute(stmt)


def _row_to_dict(instance):
    result = {}
    for col in instance.__table__.columns:
        val = getattr(instance, col.name, None)
        if val is not None and col.name != 'id':
            result[col.name] = val
    return result if result else None