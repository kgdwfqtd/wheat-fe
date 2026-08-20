# -*- coding: utf-8 -*-
"""FastAPI 后端入口：真正的前后端分离 API。"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from wheat_app.config import DB_CONFIG
from wheat_app.repositories.experiment_repository import (
    add_operation,
    create_experiment_base,
    delete_experiment_base,
    get_all_bases,
    get_all_plots,
    get_all_records,
    get_base_by_code,
    get_completion_stats,
    get_operations,
    get_plot_by_code,
    get_record_by_id,
    get_record_owner,
    get_treatment_table_matrix,
    query_data_view,
    update_record_by_id,
    upsert_record,
    update_experiment_base,
    save_weather_data,
    get_weather_data,
    get_latest_weather,
    delete_weather_data,
)

import psycopg2

ALLOWED_TABLES = {
    "soil_data",
    "phenology",
    "emergence",
    "agronomic_traits",
    "physiological",
    "yield_data",
    "quality_data",
    "operation_log",
    "fertilization_log",
    "field_management",
}


def _clean_nan(obj):
    """递归清理对象中的 NaN 值，将其转换为 None"""
    if isinstance(obj, float) and pd.isna(obj):
        return None
    elif isinstance(obj, dict):
        return {k: _clean_nan(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_clean_nan(item) for item in obj]
    return obj


def _df_to_clean_dict(df) -> list[dict]:
    """将 DataFrame 转换为干净的字典列表（无 NaN）"""
    if df is None or df.empty:
        return []
    records = df.to_dict(orient="records")
    return [_clean_nan(r) for r in records]


def _success_response(data: Any = None, message: str = "ok") -> dict[str, Any]:
    payload: dict[str, Any] = {"success": True, "message": message}
    if data is not None:
        payload["data"] = data
    return payload


class ExperimentBaseCreateRequest(BaseModel):
    base_code: str = Field(..., min_length=14, max_length=14)
    base_name: str = Field(..., min_length=1)
    admin_code: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    remarks: str = ""


class PlotCreateRequest(BaseModel):
    block: str = Field(..., min_length=1)
    treatment: str = Field(..., min_length=1)
    plot_code: str | None = None
    area_m2: float = 20.0
    field_name: str = ""
    base_code: str = "000000000000"
    # 播种与试验设计元数据
    variety: str = ""
    previous_crop: str = ""
    soil_type: str = ""
    sowing_date: str | None = None
    sowing_rate: float | None = None
    row_spacing: float | None = None
    sowing_depth: float | None = None
    sowing_method: str = ""
    plot_orientation: str = ""
    replication: int | None = None
    experiment_year: int | None = None


class FertilizationLogRequest(BaseModel):
    plot_code: str
    application_date: str
    growth_stage: str = ""
    fertilizer_type: str
    application_method: str = ""
    concentration: float | None = None
    dilution_ratio: float | None = None
    dose_per_plot: float | None = None
    dose_per_mu: float | None = None
    active_iron_amount: float | None = None
    spray_volume: float | None = None
    application_times: int = 1
    operator: str = ""
    weather_temp: float | None = None
    weather_humidity: float | None = None
    remarks: str = ""


class FieldManagementRequest(BaseModel):
    plot_code: str | None = None
    base_code: str = "000000000000"
    management_date: str
    management_type: str
    input_name: str = ""
    input_amount: float | None = None
    input_unit: str = ""
    method: str = ""
    operator: str = ""
    remarks: str = ""


class TableRecordRequest(BaseModel):
    plot_code: str | None = None
    base_code: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


def _get_plot_id(plot_code: str, base_code: str | None = None) -> int:
    plot = get_plot_by_code(plot_code, base_code=base_code)
    if plot is None:
        detail = f"小区 {plot_code} 不存在" if not base_code else f"基地 {base_code} 下小区 {plot_code} 不存在"
        raise HTTPException(status_code=404, detail=detail)
    return int(plot["id"])


def _validate_base_code(base_code: str) -> str:
    # 兼容旧版本默认基地编号（12 位全 0），其余必须为 14 位数字
    if base_code == "000000000000":
        return base_code
    if not re.fullmatch(r"\d{6}\d{2}\d{4}\d{2}", base_code):
        raise HTTPException(
            status_code=400,
            detail="基地编号格式错误，必须为 6位县级行政区划代码 + 2位基地编号 + 年 + 月，例如 510105010202608",
        )
    return base_code


app = FastAPI(
    title="纳米铁肥小麦试验记录系统 API",
    version="1.0.0",
    description="用于田间数据采集与管理的 FastAPI 后端",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注意：静态前端服务在文件末尾挂载，确保 API 路由优先匹配
@app.get("/api/v1/health")
async def health_check():
    return _success_response(
        {
            "status": "ok",
            "service": "backend",
            "message": "FastAPI backend is running",
        },
        message="ok",
    )


@app.get("/api/v1/config")
async def get_backend_config():
    return _success_response(
        {
            "app_name": "纳米铁肥小麦试验记录系统",
            "version": "1.0.0",
            "backend": "FastAPI",
            "frontend": "static-html",
            "tables": sorted(ALLOWED_TABLES),
        },
        message="config loaded",
    )


@app.get("/api/v1/bases")
async def list_bases():
    bases_df = get_all_bases()
    if bases_df is None or bases_df.empty:
        return _success_response([], message="no bases")
    return _success_response(_df_to_clean_dict(bases_df), message="bases loaded")


@app.get("/api/v1/bases/{base_code}/details")
async def get_base_details(base_code: str):
    base = get_base_by_code(base_code)
    if not base:
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")
    
    plots_df = get_all_plots(base_code=base_code)
    plot_count = len(plots_df) if plots_df is not None and not plots_df.empty else 0
    
    block_counts = {}
    treatment_counts = {}
    if plots_df is not None and not plots_df.empty:
        for _, row in plots_df.iterrows():
            block = row['block']
            treatment = row['treatment']
            block_counts[block] = block_counts.get(block, 0) + 1
            treatment_counts[treatment] = treatment_counts.get(treatment, 0) + 1
    
    crop_stats = {}
    for table_name in ['soil_data', 'phenology_data', 'yield_data', 'quality_data']:
        try:
            records = get_all_records(table_name)
            if records is not None and not records.empty:
                crop_stats[table_name] = len(records)
        except Exception:
            crop_stats[table_name] = 0
    
    try:
        operations = get_all_records('operation_log')
        operation_count = len(operations) if operations is not None and not operations.empty else 0
    except Exception:
        operation_count = 0
    
    details = {
        "base_code": base_code,
        "base_name": base.get('base_name', ''),
        "admin_code": base.get('admin_code', ''),
        "address": base.get('address', '') or '',
        "latitude": base.get('latitude'),
        "longitude": base.get('longitude'),
        "plot_count": plot_count,
        "block_counts": block_counts,
        "treatment_counts": treatment_counts,
        "crop_stats": crop_stats,
        "operation_count": operation_count
    }
    return _success_response(details, message="base details loaded")


@app.get("/api/v1/bases/{base_code}")
async def get_base(base_code: str):
    base = get_base_by_code(base_code)
    if not base:
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")
    return _success_response(base, message="base loaded")


@app.put("/api/v1/bases/{base_code}")
async def update_base(base_code: str, payload: ExperimentBaseCreateRequest):
    _validate_base_code(base_code)
    if not get_base_by_code(base_code):
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")
    updated = update_experiment_base(
        base_code=base_code,
        base_name=payload.base_name,
        admin_code=payload.admin_code or payload.base_code[:6],
        address=payload.address,
        latitude=payload.latitude,
        longitude=payload.longitude,
        remarks=payload.remarks,
    )
    return _success_response(updated, message="base updated")


@app.post("/api/v1/bases")
async def create_base(payload: ExperimentBaseCreateRequest):
    base_code = _validate_base_code(payload.base_code)
    if get_base_by_code(base_code):
        raise HTTPException(status_code=409, detail=f"基地 {base_code} 已存在")

    create_experiment_base(
        base_code=base_code,
        base_name=payload.base_name,
        admin_code=payload.admin_code or base_code[:6],
        address=payload.address or '',
        latitude=payload.latitude,
        longitude=payload.longitude,
        remarks=payload.remarks,
    )
    return _success_response({"base_code": base_code}, message="base created")


@app.delete("/api/v1/bases/{base_code}")
async def delete_base(base_code: str):
    # 删除操作允许删除任意存在的基地（跳过编号格式校验），
    # 因为历史或示例数据可能不满足当前校验规则。
    if not get_base_by_code(base_code):
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")
    delete_experiment_base(base_code)
    return _success_response({"base_code": base_code}, message="base deleted")


@app.get("/api/v1/plots")
async def list_plots(base_code: str | None = None):
    plots_df = get_all_plots(base_code=base_code) if base_code else get_all_plots()
    if plots_df is None or plots_df.empty:
        return _success_response([], message="no plots")
    return _success_response(_df_to_clean_dict(plots_df), message="plots loaded")


@app.post("/api/v1/plots")
async def create_plot(payload: PlotCreateRequest):
    base_code = _validate_base_code(payload.base_code)
    if not get_base_by_code(base_code):
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在，请先创建该试验基地")

    plot_code = payload.plot_code or f"{payload.block}-{payload.treatment}"

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            # 同一基地下唯一性检查（不同基地允许存在相同 plot_code）
            cur.execute("SELECT 1 FROM plots WHERE base_code = %s AND plot_code = %s", (base_code, plot_code))
            if cur.fetchone() is not None:
                raise HTTPException(status_code=409, detail=f"小区 {plot_code} 在该基地已存在")
            cur.execute(
                """
                INSERT INTO plots (base_code, block, treatment, plot_code, area_m2, field_name,
                                   variety, previous_crop, soil_type, sowing_date, sowing_rate,
                                   row_spacing, sowing_depth, sowing_method, plot_orientation,
                                   replication, experiment_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (base_code, payload.block, payload.treatment, plot_code, payload.area_m2, payload.field_name,
                 payload.variety, payload.previous_crop, payload.soil_type, payload.sowing_date or None,
                 payload.sowing_rate, payload.row_spacing, payload.sowing_depth,
                 payload.sowing_method, payload.plot_orientation, payload.replication, payload.experiment_year),
            )
    return _success_response({"base_code": base_code, "plot_code": plot_code}, message="plot created")


@app.post("/api/v1/plots/init")
async def init_plots(payload: dict):
    base_code = payload.get("base_code")
    num_blocks = payload.get("num_blocks", 3)
    num_treatments = payload.get("num_treatments", 6)
    
    if not base_code:
        raise HTTPException(status_code=400, detail="缺少 base_code 参数")
    if not get_base_by_code(base_code):
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")
    
    # 限制数量
    num_blocks = min(max(1, num_blocks), 10)
    num_treatments = min(max(1, num_treatments), 10)
    
    # 区组名称
    block_names = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    # 处理名称
    treatment_names = ["CK", "FS", "NF-0.5", "NF-1.0", "NF-1.5", "NF-2.0", "NF-2.5", "NF-3.0", "NF-3.5", "NF-4.0"]
    
    created = 0
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            for i in range(num_blocks):
                for j in range(num_treatments):
                    block = block_names[i]
                    treatment = treatment_names[j]
                    plot_code = f"{block}-{treatment}"
                    # plots 的唯一约束是 (base_code, plot_code) 与 (base_code, block, treatment)
                    cur.execute(
                        """
                        INSERT INTO plots (base_code, block, treatment, plot_code, area_m2)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (base_code, plot_code) DO NOTHING
                        """,
                        (base_code, block, treatment, plot_code, 20.0),
                    )
                    if cur.rowcount > 0:
                        created += 1
    
    return _success_response({
        "base_code": base_code,
        "num_blocks": num_blocks,
        "num_treatments": num_treatments,
        "created": created
    }, message=f"initialized {created} plots")


@app.get("/api/v1/plots/{plot_code}")
async def get_plot(plot_code: str):
    plots_df = get_all_plots()
    if plots_df is None or plots_df.empty:
        raise HTTPException(status_code=404, detail=f"小区 {plot_code} 不存在")

    match = plots_df[plots_df["plot_code"] == plot_code]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"小区 {plot_code} 不存在")

    return _success_response(match.iloc[0].to_dict(), message="plot loaded")


@app.put("/api/v1/plots/{plot_code}")
async def update_plot(plot_code: str, payload: PlotCreateRequest):
    # 小区编号在不同基地可重复，更新必须按「基地 + 编号」定位，避免改到其它基地同名小区
    base_code = _validate_base_code(payload.base_code)
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM plots WHERE base_code = %s AND plot_code = %s", (base_code, plot_code))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail=f"小区 {plot_code} 在基地 {base_code} 不存在")
            existing_id = row[0]

            new_code = payload.plot_code or plot_code
            if new_code != plot_code:
                cur.execute("SELECT 1 FROM plots WHERE base_code = %s AND plot_code = %s", (base_code, new_code))
                if cur.fetchone() is not None:
                    raise HTTPException(status_code=409, detail=f"小区 {new_code} 在该基地已存在")

            cur.execute(
                """
                UPDATE plots
                SET block = %s,
                    treatment = %s,
                    plot_code = %s,
                    area_m2 = %s,
                    field_name = %s,
                    variety = %s,
                    previous_crop = %s,
                    soil_type = %s,
                    sowing_date = %s,
                    sowing_rate = %s,
                    row_spacing = %s,
                    sowing_depth = %s,
                    sowing_method = %s,
                    plot_orientation = %s,
                    replication = %s,
                    experiment_year = %s
                WHERE id = %s
                """,
                (
                    payload.block,
                    payload.treatment,
                    new_code,
                    payload.area_m2,
                    payload.field_name,
                    payload.variety,
                    payload.previous_crop,
                    payload.soil_type,
                    payload.sowing_date or None,
                    payload.sowing_rate,
                    payload.row_spacing,
                    payload.sowing_depth,
                    payload.sowing_method,
                    payload.plot_orientation,
                    payload.replication,
                    payload.experiment_year,
                    existing_id,
                ),
            )

    return _success_response({"plot_code": payload.plot_code or plot_code}, message="plot updated")


@app.get("/api/v1/dashboard")
async def get_dashboard():
    ops_df = get_operations(limit=10)
    plots_df = get_all_plots()
    bases_df = get_all_bases()
    return _success_response(
        {
            "stats": get_completion_stats(),
            "treatment_matrix": get_treatment_table_matrix(),
            "recent_operations": _df_to_clean_dict(ops_df) if ops_df is not None else [],
            "total_plots": int(len(plots_df)) if plots_df is not None else 0,
            "base_count": int(len(bases_df)) if bases_df is not None else 0,
        },
        message="dashboard loaded",
    )


# ============================================================
# 铁肥施用记录 fertilization_log CRUD
# ============================================================
_FERT_LOG_FIELDS = [
    "application_date", "growth_stage", "fertilizer_type", "application_method",
    "concentration", "dilution_ratio", "dose_per_plot", "dose_per_mu",
    "active_iron_amount", "spray_volume", "application_times",
    "operator", "weather_temp", "weather_humidity", "remarks",
]


@app.get("/api/v1/fertilization")
async def list_fertilization_logs(base_code: str | None = None, plot_code: str | None = None):
    """查询铁肥施用记录列表，可按基地或小区筛选。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT fl.id, fl.plot_id, fl.base_code, fl.application_date, fl.growth_stage,
                       fl.fertilizer_type, fl.application_method, fl.concentration,
                       fl.dilution_ratio, fl.dose_per_plot, fl.dose_per_mu,
                       fl.active_iron_amount, fl.spray_volume, fl.application_times,
                       fl.operator, fl.weather_temp, fl.weather_humidity, fl.remarks,
                       fl.created_at, p.plot_code, p.block, p.treatment
                FROM fertilization_log fl
                LEFT JOIN plots p ON p.id = fl.plot_id
                WHERE 1=1
            """
            params = []
            if base_code:
                sql += " AND fl.base_code = %s"
                params.append(base_code)
            if plot_code:
                sql += " AND p.plot_code = %s"
                params.append(plot_code)
            sql += " ORDER BY fl.application_date DESC, fl.id DESC"
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
    return _success_response([dict(zip(cols, r)) for r in rows], message="fertilization logs")


@app.post("/api/v1/fertilization")
async def create_fertilization_log(payload: FertilizationLogRequest,
                                   authorization: str | None = Header(default=None)):
    """新增铁肥施用记录。"""
    user = _get_current_user(authorization)
    plot = get_plot_by_code(payload.plot_code)
    if plot is None:
        raise HTTPException(status_code=404, detail=f"小区 {payload.plot_code} 不存在")
    plot_id = int(plot["id"])
    base_code = plot.get("base_code") or "000000000000"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO fertilization_log (plot_id, base_code, application_date, growth_stage,
                    fertilizer_type, application_method, concentration, dilution_ratio,
                    dose_per_plot, dose_per_mu, active_iron_amount, spray_volume,
                    application_times, operator, weather_temp, weather_humidity, remarks,
                    created_by, updated_by, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (plot_id, base_code, payload.application_date, payload.growth_stage,
                 payload.fertilizer_type, payload.application_method, payload.concentration,
                 payload.dilution_ratio, payload.dose_per_plot, payload.dose_per_mu,
                 payload.active_iron_amount, payload.spray_volume, payload.application_times,
                 payload.operator, payload.weather_temp, payload.weather_humidity, payload.remarks,
                 user["username"], user["username"]),
            )
            new_id = cur.fetchone()[0]
    return _success_response({"id": new_id}, message="fertilization log created")


@app.put("/api/v1/fertilization/{log_id}")
async def update_fertilization_log(log_id: int, payload: FertilizationLogRequest,
                                   authorization: str | None = Header(default=None)):
    """更新铁肥施用记录。"""
    user = _get_current_user(authorization)
    existing = get_record_by_id("fertilization_log", log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"施用记录 {log_id} 不存在")
    _check_edit_permission(user, existing.get("updated_by"))
    plot = get_plot_by_code(payload.plot_code)
    if plot is None:
        raise HTTPException(status_code=404, detail=f"小区 {payload.plot_code} 不存在")
    plot_id = int(plot["id"])
    base_code = plot.get("base_code") or "000000000000"
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE fertilization_log SET
                    plot_id=%s, base_code=%s, application_date=%s, growth_stage=%s,
                    fertilizer_type=%s, application_method=%s, concentration=%s,
                    dilution_ratio=%s, dose_per_plot=%s, dose_per_mu=%s,
                    active_iron_amount=%s, spray_volume=%s, application_times=%s,
                    operator=%s, weather_temp=%s, weather_humidity=%s, remarks=%s,
                    updated_by=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (plot_id, base_code, payload.application_date, payload.growth_stage,
                 payload.fertilizer_type, payload.application_method, payload.concentration,
                 payload.dilution_ratio, payload.dose_per_plot, payload.dose_per_mu,
                 payload.active_iron_amount, payload.spray_volume, payload.application_times,
                 payload.operator, payload.weather_temp, payload.weather_humidity, payload.remarks,
                 user["username"], log_id),
            )
    return _success_response({"id": log_id}, message="fertilization log updated")


@app.delete("/api/v1/fertilization/{log_id}")
async def delete_fertilization_log(log_id: int, authorization: str | None = Header(default=None)):
    """删除铁肥施用记录。"""
    user = _get_current_user(authorization)
    existing = get_record_by_id("fertilization_log", log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"施用记录 {log_id} 不存在")
    _check_edit_permission(user, existing.get("updated_by"))
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fertilization_log WHERE id=%s", (log_id,))
    return _success_response({"id": log_id}, message="fertilization log deleted")


# ============================================================
# 田间管理记录 field_management CRUD
# ============================================================
@app.get("/api/v1/field-management")
async def list_field_management(base_code: str | None = None, plot_code: str | None = None):
    """查询田间管理记录列表。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT fm.id, fm.plot_id, fm.base_code, fm.management_date, fm.management_type,
                       fm.input_name, fm.input_amount, fm.input_unit, fm.method,
                       fm.operator, fm.remarks, fm.created_at,
                       p.plot_code, p.block, p.treatment
                FROM field_management fm
                LEFT JOIN plots p ON p.id = fm.plot_id
                WHERE 1=1
            """
            params = []
            if base_code:
                sql += " AND fm.base_code = %s"
                params.append(base_code)
            if plot_code:
                sql += " AND p.plot_code = %s"
                params.append(plot_code)
            sql += " ORDER BY fm.management_date DESC, fm.id DESC"
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
    return _success_response([dict(zip(cols, r)) for r in rows], message="field management logs")


@app.post("/api/v1/field-management")
async def create_field_management(payload: FieldManagementRequest,
                                  authorization: str | None = Header(default=None)):
    """新增田间管理记录。"""
    user = _get_current_user(authorization)
    plot_id = None
    base_code = payload.base_code or "000000000000"
    if payload.plot_code:
        plot = get_plot_by_code(payload.plot_code)
        if plot is None:
            raise HTTPException(status_code=404, detail=f"小区 {payload.plot_code} 不存在")
        plot_id = int(plot["id"])
        base_code = plot.get("base_code") or base_code
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO field_management (plot_id, base_code, management_date, management_type,
                    input_name, input_amount, input_unit, method, operator, remarks,
                    created_by, updated_by, created_at, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                RETURNING id
                """,
                (plot_id, base_code, payload.management_date, payload.management_type,
                 payload.input_name, payload.input_amount, payload.input_unit,
                 payload.method, payload.operator, payload.remarks,
                 user["username"], user["username"]),
            )
            new_id = cur.fetchone()[0]
    return _success_response({"id": new_id}, message="field management created")


@app.put("/api/v1/field-management/{log_id}")
async def update_field_management(log_id: int, payload: FieldManagementRequest,
                                  authorization: str | None = Header(default=None)):
    """更新田间管理记录。"""
    plot_id = None
    base_code = payload.base_code or "000000000000"
    if payload.plot_code:
        plot = get_plot_by_code(payload.plot_code)
        if plot is None:
            raise HTTPException(status_code=404, detail=f"小区 {payload.plot_code} 不存在")
        plot_id = int(plot["id"])
        base_code = plot.get("base_code") or base_code
    user = _get_current_user(authorization)
    existing = get_record_by_id("field_management", log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"管理记录 {log_id} 不存在")
    _check_edit_permission(user, existing.get("updated_by"))
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE field_management SET
                    plot_id=%s, base_code=%s, management_date=%s, management_type=%s,
                    input_name=%s, input_amount=%s, input_unit=%s, method=%s,
                    operator=%s, remarks=%s, updated_by=%s, updated_at=CURRENT_TIMESTAMP
                WHERE id=%s
                """,
                (plot_id, base_code, payload.management_date, payload.management_type,
                 payload.input_name, payload.input_amount, payload.input_unit,
                 payload.method, payload.operator, payload.remarks,
                 user["username"], log_id),
            )
    return _success_response({"id": log_id}, message="field management updated")


@app.delete("/api/v1/field-management/{log_id}")
async def delete_field_management(log_id: int, authorization: str | None = Header(default=None)):
    """删除田间管理记录。"""
    user = _get_current_user(authorization)
    existing = get_record_by_id("field_management", log_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"管理记录 {log_id} 不存在")
    _check_edit_permission(user, existing.get("updated_by"))
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM field_management WHERE id=%s", (log_id,))
    return _success_response({"id": log_id}, message="field management deleted")


@app.get("/api/v1/table/{table_name}")
async def get_table_data(table_name: str, base_code: str | None = None):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"不支持的数据表: {table_name}")

    df = get_all_records(table_name)
    if df is None or df.empty:
        return _success_response([], message=f"{table_name} no data")
    if base_code and "base_code" in df.columns:
        df = df[df["base_code"] == base_code].copy()
    return _success_response(_df_to_clean_dict(df), message=f"{table_name} loaded")


@app.post("/api/v1/table/{table_name}")
async def upsert_table_record(table_name: str, payload: TableRecordRequest,
                              authorization: str | None = Header(default=None)):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"不支持的数据表: {table_name}")
    if not payload.data:
        raise HTTPException(status_code=400, detail="请求体缺少 data 字段或为空")

    # 登录校验（桌面端主界面强制登录，api() 已附带 token）
    user = _get_current_user(authorization)

    if table_name == "operation_log":
        record = dict(payload.data)
        if payload.plot_code:
            record["plot_id"] = _get_plot_id(payload.plot_code, payload.base_code)
        # operation_log 为追加式日志：新增不校验归属，但记录录入人
        add_operation(**record, created_by=user["username"], updated_by=user["username"])
        return _success_response({"table": table_name, "plot_code": payload.plot_code}, message="operation saved")

    if payload.plot_code is None:
        raise HTTPException(status_code=400, detail="该表需要提供 plot_code")

    plot_id = _get_plot_id(payload.plot_code, payload.base_code)
    data = dict(payload.data)

    # emergence 表自动计算 rate_7d / rate_14d（避免手算错误）
    if table_name == "emergence":
        try:
            seeds = float(data.get("seeds_sown") or 0)
            if seeds > 0:
                if data.get("emerged_7d") is not None:
                    data["rate_7d"] = round(float(data["emerged_7d"]) / seeds * 100, 2)
                if data.get("emerged_14d") is not None:
                    data["rate_14d"] = round(float(data["emerged_14d"]) / seeds * 100, 2)
        except (TypeError, ValueError):
            pass

    # yield_data 自动计算 standardized_yield（按 13% 标准含水率折算 actual_yield）
    if table_name == "yield_data":
        try:
            ay = data.get("actual_yield")
            mc = data.get("moisture_content")
            if ay is not None and mc is not None:
                ay_f = float(ay)
                mc_f = float(mc)
                data["standardized_yield"] = round(ay_f * (100 - mc_f) / (100 - 13), 2)
        except (TypeError, ValueError):
            pass

    # 权限：已有记录（覆盖保存）时校验归属 = 管理员或本人（updated_by）；
    # 无记录（None）视为新建，任何登录用户均可创建。
    extra_keys = dict(payload.extra) or None
    owner = get_record_owner(table_name, plot_id, extra_keys=extra_keys)
    _check_edit_permission(user, owner, record_exists=owner is not None)
    upsert_record(table_name, plot_id, data, extra_keys=extra_keys,
                  created_by=user["username"], updated_by=user["username"])
    return _success_response({"table": table_name, "plot_code": payload.plot_code}, message="record saved")


@app.put("/api/v1/table/{table_name}/{record_id}")
async def update_table_record(table_name: str, record_id: int, payload: TableRecordRequest,
                              authorization: str | None = Header(default=None)):
    """按主键 id 更新日志表记录（操作日志/铁肥施用/田间管理），带归属权限校验。"""
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"不支持的数据表: {table_name}")
    if not payload.data:
        raise HTTPException(status_code=400, detail="请求体缺少 data 字段或为空")

    user = _get_current_user(authorization)
    existing = get_record_by_id(table_name, record_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"记录不存在: {table_name}#{record_id}")
    _check_edit_permission(user, existing.get("updated_by"))

    update_record_by_id(table_name, record_id, dict(payload.data), updated_by=user["username"])
    return _success_response({"table": table_name, "record_id": record_id}, message="record updated")


@app.get("/api/v1/data-view")
async def get_data_view(table: str | None = None, base_code: str | None = None,
                        authorization: str | None = Header(default=None)):
    """「数据查看」聚合接口：返回各数据表记录（含小区/处理/录入人/更新时间与 editable 标志）。"""
    user = _get_current_user(authorization)
    tables = [table] if table else sorted(ALLOWED_TABLES)
    rows: list[dict] = []
    for t in tables:
        if t not in ALLOWED_TABLES:
            raise HTTPException(status_code=404, detail=f"不支持的数据表: {t}")
        try:
            recs = query_data_view(t, base_code=base_code)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"不支持的数据表: {t}")
        for r in recs:
            r = dict(r)
            r["table_name"] = t
            r["record_id"] = r.get("id")
            owner = r.get("updated_by")
            r["editable"] = (user["role"] == "admin") or bool(owner and owner == user["username"])
            rows.append(r)
    return _success_response(rows, message="data view loaded")


@app.get("/api/v1/example")
async def get_example_data():
    example: dict[str, Any] = {}
    for table_name in sorted(ALLOWED_TABLES):
        frame = get_all_records(table_name)
        if frame is not None and not frame.empty:
            example[table_name] = _df_to_clean_dict(frame.head(5))
    return _success_response(example, message="example data loaded")


# ============================================================
# 天气数据 API
# ============================================================

import urllib.request
import urllib.parse
import gzip
import json as json_mod
from datetime import date, timedelta

# 和风天气 API 配置
# 开发者ID: Q98C59B853  |  凭据ID: T9PREDFNAY  |  API Host: ma2k5qpu46.re.qweatherapi.com
QWEATHER_API_KEY = os.environ.get("QWEATHER_API_KEY", "12460658075d4c5489667d2ad1885ea4")
QWEATHER_API_HOST = os.environ.get("QWEATHER_API_HOST", "ma2k5qpu46.re.qweatherapi.com")
# 地理编码API（商用版也使用自定义Host）
QWEATHER_GEO_URL = f"https://{QWEATHER_API_HOST}/v2/city/location"
QWEATHER_NOW_URL = f"https://{QWEATHER_API_HOST}/v7/weather/now"
QWEATHER_7D_URL = f"https://{QWEATHER_API_HOST}/v7/weather/7d"
QWEATHER_3D_URL = f"https://{QWEATHER_API_HOST}/v7/weather/3d"
# 新版空气质量API (v7的air/now已废弃，必须使用v8的airquality/v1/current)
QWEATHER_AIR_NEW_URL = f"https://{QWEATHER_API_HOST}/airquality/v1/current"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def _qweather_text_to_code(text):
    """将和风天气天气文字描述映射为图标代码 (兼容getWeatherIcon)."""
    mapping = {
        "晴": 0,
        "多云": 2, "少云": 2, "局部多云": 2,
        "阴": 3,
        "小雨": 61, "中雨": 63, "大雨": 65,
        "暴雨": 65, "大暴雨": 65, "特大暴雨": 65,
        "雷阵雨": 95, "雷阵雨伴有冰雹": 96,
        "小雪": 71, "中雪": 73, "大雪": 75, "暴雪": 75,
        "雾": 45, "霾": 45, "沙尘": 45, "浮尘": 45,
        "小到中雨": 61, "中到大雨": 63, "大到暴雨": 65,
        "阵雨": 80, "雷阵雨伴冰雹": 96,
    }
    if not text:
        return 3
    # 尝试精确匹配，再尝试包含匹配
    if text in mapping:
        return mapping[text]
    for key, code in mapping.items():
        if key in text:
            return code
    return 3

# 风向中文转角度
_WIND_DIR_MAP = {
    "北": 0, "北东北": 22.5, "东北": 45, "东东北": 67.5,
    "东": 90, "东东南": 112.5, "东南": 135, "南东南": 157.5,
    "南": 180, "南西南": 202.5, "西南": 225, "西西南": 247.5,
    "西": 270, "西西北": 292.5, "西北": 315, "北西北": 337.5,
    "东北风": 45, "东南风": 135, "西南风": 225, "西北风": 315,
    "东风": 90, "南风": 180, "西风": 270, "北风": 0,
    "东北": 45, "东南": 135, "西南": 225, "西北": 315,
    "东": 90, "南": 180, "西": 270, "北": 0,
}

def _wind_dir_to_deg(text):
    """将和风天气风向文字转换为角度（度）。"""
    if not text:
        return None
    text = str(text).strip()
    if text in _WIND_DIR_MAP:
        return _WIND_DIR_MAP[text]
    # 尝试匹配包含"风"的
    for k, v in _WIND_DIR_MAP.items():
        if k in text:
            return v
    return None

def _wind_deg_to_text(deg):
    """将角度转换为中文风向（如 0->北风, 90->东风）。"""
    if deg is None:
        return None
    try:
        deg = float(deg) % 360
    except (TypeError, ValueError):
        return None
    dirs = ["北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风"]
    idx = int((deg + 22.5) // 45) % 8
    return dirs[idx]

def _aqi_category(level):
    """根据AQI数值返回中文等级和颜色。"""
    try:
        a = int(level)
    except (TypeError, ValueError):
        return None
    if a <= 50:
        return {"category": "优", "color": "#4caf50"}
    if a <= 100:
        return {"category": "良", "color": "#cddc39"}
    if a <= 150:
        return {"category": "轻度污染", "color": "#ffb300"}
    if a <= 200:
        return {"category": "中度污染", "color": "#fb8c00"}
    if a <= 300:
        return {"category": "重度污染", "color": "#e53935"}
    return {"category": "严重污染", "color": "#8e24aa"}

def _safe_float(val):
    """安全转float，失败返回None。"""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

def _safe_int(val):
    """安全转int，失败返回None。"""
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None

def _http_get_json(url, timeout=10, extra_headers=None):
    """执行HTTP GET请求并返回JSON（支持gzip解压）。"""
    headers = {
        "User-Agent": "WheatFe/1.0",
        "Accept-Encoding": "gzip",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        # 处理gzip压缩响应
        if resp.headers.get("Content-Encoding") == "gzip" or (len(raw) > 2 and raw[:2] == b'\x1f\x8b'):
            raw = gzip.decompress(raw)
        return json_mod.loads(raw.decode())

def _parse_qweather_air_v8(data):
    """解析和风天气v8空气质量API返回数据，统一为前端使用的格式。"""
    if not data or not isinstance(data, dict):
        return None
    indexes = data.get("indexes") or []
    # 优先取中国AQI标准(cn-mee)，其次取第一个
    cn_idx = next((i for i in indexes if i.get("code") == "cn-mee"), None)
    idx = cn_idx or (indexes[0] if indexes else None)
    if not idx:
        return None
    aqi_val = _safe_int(idx.get("aqi"))
    color_obj = idx.get("color") or {}
    css_color = None
    if color_obj:
        r = int(color_obj.get("red", 0))
        g = int(color_obj.get("green", 0))
        b = int(color_obj.get("blue", 0))
        a = float(color_obj.get("alpha", 1))
        css_color = f"rgba({r},{g},{b},{a})"
    cat_info = _aqi_category(aqi_val) if aqi_val is not None else None
    # 污染物浓度
    pollutant_map = {}
    for p in data.get("pollutants") or []:
        code = p.get("code")
        conc = p.get("concentration") or {}
        val = _safe_float(conc.get("value"))
        unit = conc.get("unit", "")
        if code and val is not None:
            pollutant_map[code] = {"value": val, "unit": unit}
    primary = idx.get("primaryPollutant") or {}
    primary_code = primary.get("code") if isinstance(primary, dict) else primary
    return {
        "aqi": aqi_val,
        "category": idx.get("category") or (cat_info["category"] if cat_info else None),
        "color": css_color or (cat_info["color"] if cat_info else None),
        "primary": primary_code,
        "pm25": pollutant_map.get("pm2p5", {}).get("value"),
        "pm10": pollutant_map.get("pm10", {}).get("value"),
        "no2": pollutant_map.get("no2", {}).get("value"),
        "so2": pollutant_map.get("so2", {}).get("value"),
        "co": pollutant_map.get("co", {}).get("value"),
        "o3": pollutant_map.get("o3", {}).get("value"),
    }

def _get_qweather_location(lat, lon):
    """通过经纬度获取和风天气LocationID。"""
    # 优先用缓存（基地纬度经度不变）
    cache_key = f"qid_{round(lat, 3)}_{round(lon, 3)}"
    if hasattr(_get_qweather_location, 'cache') and cache_key in _get_qweather_location.cache:
        return _get_qweather_location.cache[cache_key]
    
    url = f"{QWEATHER_GEO_URL}?location={lon},{lat}&key={QWEATHER_API_KEY}"
    data = _http_get_json(url, timeout=8)
    
    location_id = None
    if data.get("code") == "200" and data.get("location"):
        location_id = data["location"][0].get("id")
    
    if not hasattr(_get_qweather_location, 'cache'):
        _get_qweather_location.cache = {}
    _get_qweather_location.cache[cache_key] = location_id
    return location_id

def _fetch_qweather_weather(base_code, lat, lon):
    """从和风天气获取天气数据（当前+7天预报）。优先使用坐标直接查询。"""
    today = date.today()
    daily_data = []
    
    # 商用API支持location=经度,纬度直接查询
    location_param = f"{lon},{lat}"
    extra_param = "&lang=zh&unit=m"
    
    # 1. 获取7天预报
    url_7d = f"{QWEATHER_7D_URL}?location={location_param}&key={QWEATHER_API_KEY}{extra_param}"
    data_7d = _http_get_json(url_7d, timeout=10)
    
    if data_7d.get("code") == "200" and data_7d.get("daily"):
        for day_entry in data_7d["daily"]:
            fx_date = day_entry.get("fxDate", "")
            try:
                entry_date = date.fromisoformat(fx_date)
                if entry_date < today - timedelta(days=1):
                    continue
            except (ValueError, TypeError):
                continue
            
            text_day = day_entry.get("textDay", "")
            code = _qweather_text_to_code(text_day)
            
            weather_entry = {
                "record_date": fx_date,
                "temperature_max": float(day_entry.get("tempMax", 0)),
                "temperature_min": float(day_entry.get("tempMin", 0)),
                "precipitation": float(day_entry.get("precip", 0) or 0),
                "precipitation_probability": int(day_entry.get("precipProb", 0) or 0),
                "wind_speed_max": float(day_entry.get("windSpeedDay", 0) or 0),
                "wind_gust_max": None,
                "weather_code": code,
                "weather_description": text_day or _get_weather_description(code),
            }
            daily_data.append(weather_entry)
            
            try:
                save_weather_data(base_code, fx_date, {
                    "temperature": weather_entry["temperature_max"],
                    "temperature_max": weather_entry["temperature_max"],
                    "temperature_min": weather_entry["temperature_min"],
                    "apparent_temperature": None,
                    "humidity": None,
                    "precipitation": weather_entry["precipitation"],
                    "precipitation_probability": weather_entry["precipitation_probability"],
                    "wind_speed": weather_entry["wind_speed_max"],
                    "wind_direction": _wind_dir_to_deg(day_entry.get("windDirDay")),
                    "wind_gust": weather_entry["wind_gust_max"],
                    "weather_code": code,
                    "weather_description": weather_entry["weather_description"],
                    "is_day": True,
                })
            except Exception as e:
                print(f"Failed to save QWeather data for {fx_date}: {e}")
    
    # 2. 获取当前天气（带重试，应对偶发SSL握手超时）
    current_data = None
    url_now = f"{QWEATHER_NOW_URL}?location={location_param}&key={QWEATHER_API_KEY}{extra_param}"
    data_now = None
    for attempt in range(2):
        try:
            data_now = _http_get_json(url_now, timeout=8)
            break
        except Exception as e:
            if attempt == 0:
                print(f"QWeather now API retry: {e}")
            else:
                print(f"QWeather now API error: {e}")
    if data_now and data_now.get("code") == "200" and data_now.get("now"):
        now = data_now["now"]
        now_text = now.get("text", "")
        now_code = _qweather_text_to_code(now_text)
        wind_dir_text = now.get("windDir", "")
        wind_dir_deg = _wind_dir_to_deg(wind_dir_text)
        current_data = {
            "temperature": float(now.get("temp", 0)),
            "apparent_temperature": float(now.get("feelsLike", 0) or now.get("temp", 0)),
            "humidity": int(now.get("humidity", 0) or 0),
            "precipitation": float(now.get("precip", 0) or 0),
            "wind_speed": float(now.get("windSpeed", 0) or 0),
            "wind_direction": wind_dir_deg,
            "wind_direction_text": wind_dir_text or _wind_deg_to_text(wind_dir_deg),
            "wind_scale": now.get("windScale", ""),
            "wind_gust": float(now.get("windGust", 0) or 0),
            "pressure": _safe_float(now.get("pressure")),
            "visibility": _safe_float(now.get("vis")),
            "cloud": _safe_float(now.get("cloud")),
            "dew_point": _safe_float(now.get("dew")),
            "weather_code": now_code,
            "weather_description": now_text or _get_weather_description(now_code),
            "is_day": True,
            "time": now.get("obsTime"),
        }
        # 保存当日观测到数据库，便于后续补充历史数据
        try:
            today_str = today.isoformat()
            save_weather_data(base_code, today_str, {
                "temperature": current_data.get("temperature"),
                "temperature_max": current_data.get("temperature"),
                "temperature_min": current_data.get("temperature"),
                "apparent_temperature": current_data.get("apparent_temperature"),
                "humidity": current_data.get("humidity"),
                "precipitation": current_data.get("precipitation"),
                "precipitation_probability": None,
                "wind_speed": current_data.get("wind_speed"),
                "wind_direction": current_data.get("wind_direction"),
                "wind_gust": current_data.get("wind_gust"),
                "weather_code": current_data.get("weather_code"),
                "weather_description": current_data.get("weather_description"),
                "is_day": current_data.get("is_day", True),
            })
        except Exception as e:
            print(f"Failed to save current QWeather observation: {e}")

    # 3. 获取空气质量数据 (使用v8新版API, v7已废弃)
    try:
        # 纬度经度各保留2位小数（API要求）
        lat_str = f"{round(lat, 2):.2f}"
        lon_str = f"{round(lon, 2):.2f}"
        url_air = f"{QWEATHER_AIR_NEW_URL}/{lat_str}/{lon_str}"
        data_air = _http_get_json(url_air, timeout=8, extra_headers={
            "X-QW-Api-Key": QWEATHER_API_KEY,
        })
        air_data = _parse_qweather_air_v8(data_air)
        if air_data:
            if current_data is None:
                current_data = {}
            current_data["air_quality"] = air_data
    except Exception as e:
        print(f"QWeather air API error: {e}")
    
    # 4. 从数据库获取历史数据（前3天）作为补充
    # QWeather商用API的3d/7d端点均为预报，历史数据需通过数据库累积
    historical_from_db = _get_historical_weather(base_code, today, days_back=3)
    seen_dates = set()
    final_daily = []
    # 先加7天预报数据
    for d in daily_data:
        if d["record_date"] not in seen_dates:
            final_daily.append(d)
            seen_dates.add(d["record_date"])
    # 再加数据库历史数据（仅保留预报中没有的过去日期）
    for d in historical_from_db:
        if d["record_date"] not in seen_dates:
            final_daily.append(d)
            seen_dates.add(d["record_date"])
    final_daily.sort(key=lambda x: x.get("record_date", ""))
    
    return current_data, final_daily

def _get_historical_weather(base_code, today, days_back=3):
    """从数据库获取历史天气数据（前N天）。"""
    result = []
    try:
        for i in range(1, days_back + 1):
            past_date = today - timedelta(days=i)
            past_str = past_date.isoformat()
            df = get_weather_data(base_code)
            if df is not None and not df.empty:
                row = df[df["record_date"] == past_str]
                if not row.empty:
                    r = row.iloc[0]
                    result.append({
                        "record_date": past_str,
                        "temperature_max": float(r.get("temperature_max", 0) or 0),
                        "temperature_min": float(r.get("temperature_min", 0) or 0),
                        "precipitation": float(r.get("precipitation", 0) or 0),
                        "precipitation_probability": float(r.get("precipitation_probability", 0) or 0),
                        "wind_speed_max": float(r.get("wind_speed", 0) or 0),
                        "wind_gust_max": None,
                        "weather_code": int(r.get("weather_code", 3) or 3),
                        "weather_description": r.get("weather_description", ""),
                    })
    except Exception as e:
        print(f"Failed to load historical weather: {e}")
    return result

def _fetch_open_meteo_weather(base_code, lat, lon):
    """从Open-Meteo获取天气数据（备用方案）。"""
    today = date.today()
    start_date = today - timedelta(days=3)
    end_date = today + timedelta(days=7)
    
    url = f"{OPEN_METEO_URL}?latitude={lat}&longitude={lon}"
    url += f"&daily=temperature_2m_max,temperature_2m_min"
    url += f",precipitation_sum,precipitation_probability_max,windspeed_10m_max,windgusts_10m_max"
    url += f",weather_code,sunrise,sunset"
    url += f"&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,windspeed_10m"
    url += f",wind_direction_10m,wind_gusts_10m,weather_code,is_day"
    url += f"&start_date={start_date}&end_date={end_date}&timezone=auto"
    
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json_mod.loads(response.read().decode())
    
    daily_data = []
    if "daily" in data:
        daily = data["daily"]
        dates = daily.get("time", [])
        for i, d in enumerate(dates):
            weather_entry = {
                "record_date": d,
                "temperature_max": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                "temperature_min": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                "precipitation": daily.get("precipitation_sum", [None])[i] if i < len(daily.get("precipitation_sum", [])) else None,
                "precipitation_probability": daily.get("precipitation_probability_max", [None])[i] if i < len(daily.get("precipitation_probability_max", [])) else None,
                "wind_speed_max": daily.get("windspeed_10m_max", [None])[i] if i < len(daily.get("windspeed_10m_max", [])) else None,
                "wind_gust_max": daily.get("windgusts_10m_max", [None])[i] if i < len(daily.get("windgusts_10m_max", [])) else None,
                "weather_code": daily.get("weather_code", [None])[i] if i < len(daily.get("weather_code", [])) else None,
            }
            weather_code = weather_entry["weather_code"]
            weather_entry["weather_description"] = _get_weather_description(weather_code)
            daily_data.append(weather_entry)
            
            try:
                weather_data = {
                    "temperature": weather_entry["temperature_max"],
                    "temperature_max": weather_entry["temperature_max"],
                    "temperature_min": weather_entry["temperature_min"],
                    "apparent_temperature": None,
                    "humidity": None,
                    "precipitation": weather_entry["precipitation"],
                    "precipitation_probability": weather_entry["precipitation_probability"],
                    "wind_speed": weather_entry["wind_speed_max"],
                    "wind_direction": None,
                    "wind_gust": weather_entry["wind_gust_max"],
                    "weather_code": weather_code,
                    "weather_description": weather_entry["weather_description"],
                    "is_day": True,
                }
                save_weather_data(base_code, d, weather_data)
            except Exception as e:
                print(f"Failed to save weather data for {d}: {e}")
    
    current_data = None
    if "current" in data:
        current = data["current"]
        current_data = {
            "temperature": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("windspeed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "wind_gust": current.get("wind_gusts_10m"),
            "weather_code": current.get("weather_code"),
            "weather_description": _get_weather_description(current.get("weather_code")),
            "is_day": current.get("is_day", True),
            "time": current.get("time"),
        }
        # 保存当日观测到数据库
        try:
            today_str = today.isoformat()
            save_weather_data(base_code, today_str, {
                "temperature": current_data.get("temperature"),
                "temperature_max": current_data.get("temperature"),
                "temperature_min": current_data.get("temperature"),
                "apparent_temperature": current_data.get("apparent_temperature"),
                "humidity": current_data.get("humidity"),
                "precipitation": current_data.get("precipitation"),
                "precipitation_probability": None,
                "wind_speed": current_data.get("wind_speed"),
                "wind_direction": current_data.get("wind_direction"),
                "wind_gust": current_data.get("wind_gust"),
                "weather_code": current_data.get("weather_code"),
                "weather_description": current_data.get("weather_description"),
                "is_day": current_data.get("is_day", True),
            })
        except Exception as e:
            print(f"Failed to save current Open-Meteo observation: {e}")
    
    return current_data, daily_data

@app.get("/api/v1/bases/{base_code}/weather")
async def get_base_weather(base_code: str, days: int = 7):
    """获取基地天气数据 - 优先使用和风天气(CMA数据源)，备用Open-Meteo。"""
    base = get_base_by_code(base_code)
    if not base:
        raise HTTPException(status_code=404, detail=f"基地 {base_code} 不存在")

    latitude = base.get('latitude')
    longitude = base.get('longitude')

    if latitude is None or longitude is None:
        weather_df = get_weather_data(base_code)
        if weather_df is not None and not weather_df.empty:
            return _success_response({
                "base_code": base_code,
                "base_name": base.get('base_name', ''),
                "has_coordinates": False,
                "message": "该基地未设置经纬度，无法获取实时天气",
                "saved_data": _df_to_clean_dict(weather_df.head(days)),
            }, message="weather data loaded")
        return _success_response({
            "base_code": base_code,
            "base_name": base.get('base_name', ''),
            "has_coordinates": False,
            "message": "该基地未设置经纬度，无法获取实时天气",
            "saved_data": [],
        }, message="no weather data")

    # 优先使用和风天气（若已配置API Key）
    if QWEATHER_API_KEY:
        try:
            print(f"Attempting QWeather API for {base_code}...")
            current_data, daily_data = _fetch_qweather_weather(base_code, latitude, longitude)
            if daily_data:
                return _success_response({
                    "base_code": base_code,
                    "base_name": base.get('base_name', ''),
                    "latitude": latitude,
                    "longitude": longitude,
                    "has_coordinates": True,
                    "current": current_data,
                    "daily": daily_data,
                    "saved_data": True,
                    "source": "qweather",
                }, message="天气数据加载成功（和风天气）")
        except Exception as e:
            print(f"QWeather API failed: {e}, falling back to Open-Meteo")

    # 备用方案：Open-Meteo
    try:
        print(f"Attempting Open-Meteo API for {base_code}...")
        current_data, daily_data = _fetch_open_meteo_weather(base_code, latitude, longitude)
        return _success_response({
            "base_code": base_code,
            "base_name": base.get('base_name', ''),
            "latitude": latitude,
            "longitude": longitude,
            "has_coordinates": True,
            "current": current_data,
            "daily": daily_data,
            "saved_data": get_weather_data(base_code) is not None and len(get_weather_data(base_code)) > 0,
            "source": "open-meteo",
        }, message="天气数据加载成功（Open-Meteo）")

    except Exception as e:
        print(f"Open-Meteo API error: {e}")
        weather_df = get_weather_data(base_code)
        if weather_df is not None and not weather_df.empty:
            weather_list = _df_to_clean_dict(weather_df.head(days))
            current = weather_list[0] if weather_list else None
            return _success_response({
                "base_code": base_code,
                "base_name": base.get('base_name', ''),
                "has_coordinates": True,
                "message": "实时天气获取失败，显示已保存数据",
                "current": current,
                "daily": weather_list,
                "source": "local",
            }, message="weather loaded from local")
        raise HTTPException(status_code=502, detail=f"天气服务暂时不可用: {str(e)}")


def _get_weather_description(code):
    """根据WMO天气代码获取描述。"""
    weather_descriptions = {
        0: "晴朗", 1: "大致晴朗", 2: "多云", 3: "阴天",
        45: "雾", 48: "冻雾",
        51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
        80: "小阵雨", 81: "中阵雨", 82: "强阵雨",
        85: "小阵雪", 86: "强阵雪",
        95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
    }
    return weather_descriptions.get(code, "未知")


# ============================================================
# 用户认证 & 权限
# ============================================================
import socket as _socket
import hashlib as _hashlib
import secrets as _secrets
import hmac as _hmac
import base64 as _base64
from datetime import datetime as _dt, timedelta as _td

# 先定义路径常量，供后续路由使用
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# ---- JWT 配置 ----
_JWT_SECRET = os.getenv("WHEAT_JWT_SECRET", "wheat-fe-secret-key-2024")
_JWT_ALGO = "HS256"
_JWT_EXPIRE_HOURS = int(os.getenv("WHEAT_JWT_EXPIRE_HOURS", "24"))

# 密码哈希使用 PBKDF2-HMAC-SHA256
_PBKDF2_ITER = 120000
_PBKDF2_ALGO = "sha256"
_PASSWORD_SALT_LEN = 16

_INITIAL_PASSWORD = "12345678"
_INITIAL_USERS = [
    # (username, real_name, role)
    ("wuhuifeng", "吴会峰", "admin"),
    ("lizhengguang", "李争光", "user"),
    ("gaozhuo", "高茁", "user"),
    ("shangwankuan", "尚万宽", "user"),
    ("xushan", "徐姗", "user"),
    # 技术员：仅手机端可登录，不能电脑端登录
    ("zhaowei", "赵伟", "technician"),
    ("qianfeng", "钱峰", "technician"),
]
_ROLE_NAMES = {"admin": "管理员", "user": "普通用户", "technician": "技术员"}
_ROLE_VALID = set(_ROLE_NAMES)


def _hash_password(password: str, salt_bytes: bytes | None = None) -> str:
    """PBKDF2 密码哈希，返回 base64(salt) + '$' + base64(digest) 格式字符串。"""
    if salt_bytes is None:
        salt_bytes = _secrets.token_bytes(_PASSWORD_SALT_LEN)
    digest = _hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt_bytes, _PBKDF2_ITER)
    salt_b64 = _base64.b64encode(salt_bytes).decode("ascii")
    digest_b64 = _base64.b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${_PBKDF2_ITER}${salt_b64}${digest_b64}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """验证密码。"""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt_bytes = _base64.b64decode(parts[2])
        expected = _base64.b64decode(parts[3])
        actual = _hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt_bytes, iterations)
        return _hmac.compare_digest(expected, actual)
    except Exception:
        return False


def _jwt_b64(data: dict) -> str:
    """手动生成 HS256 JWT（避免额外依赖 python-jose）。"""
    import json as _json
    import time as _time

    header = {"alg": _JWT_ALGO, "typ": "JWT"}
    payload = dict(data)
    if "exp" not in payload:
        payload["exp"] = int((_dt.utcnow() + _td(hours=_JWT_EXPIRE_HOURS)).timestamp())
    if "iat" not in payload:
        payload["iat"] = int(_dt.utcnow().timestamp())

    def _b64url(b: bytes) -> str:
        return _base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")

    header_json = _b64url(_json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_json = _b64url(_json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_json}.{payload_json}".encode("utf-8")
    sig = _hmac.new(_JWT_SECRET.encode("utf-8"), signing_input, _hashlib.sha256).digest()
    sig_json = _b64url(sig)
    return f"{header_json}.{payload_json}.{sig_json}"


def _jwt_decode(token: str) -> dict | None:
    """解码并验证 JWT，失败返回 None。"""
    import json as _json
    import time as _time

    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        return None

    def _b64url_decode(s: str) -> bytes:
        pad = "=" * (-len(s) % 4)
        return _base64.urlsafe_b64decode(s + pad)

    try:
        header = json_mod.loads(_b64url_decode(header_b64))
        payload = json_mod.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(sig_b64)
    except Exception:
        return None

    if header.get("alg") != _JWT_ALGO:
        return None

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = _hmac.new(_JWT_SECRET.encode("utf-8"), signing_input, _hashlib.sha256).digest()
    if not _hmac.compare_digest(expected_sig, signature):
        return None

    exp = payload.get("exp")
    if exp and int(_time.time()) > int(exp):
        return None
    return payload


# ---- 建表 & 初始化用户 ----
def _init_users():
    """创建 users 表并初始化 5 个默认用户（幂等）。"""
    conn_func = None
    # 使用和 init_db 相同的数据库连接方式
    import psycopg2 as _pg

    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    conn.autocommit = False
    try:
        cur = conn.cursor()
        # 1) 创建表（角色 CHECK 已包含 technician）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sys_users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                real_name VARCHAR(50) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user'
                    CHECK (role IN ('admin','user','technician')),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                first_login BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 2) 兼容老库：如果 sys_users 的 role CHECK 还是旧版（只有 admin/user），用 DO block 扩展它
        cur.execute(
            """
            SELECT 1
              FROM pg_constraint c
              JOIN pg_class      t ON t.oid = c.conrelid
              JOIN pg_namespace  n ON n.oid = t.relnamespace
             WHERE t.relname  = 'sys_users'
               AND n.nspname  = current_schema()
               AND c.contype  = 'c'                      -- CHECK 约束
               AND pg_get_constraintdef(c.oid) NOT LIKE '%technician%'
            LIMIT 1
            """
        )
        if cur.fetchone() is not None:
            # 找到旧 CHECK：删除所有 role 相关 CHECK 后重建（避免约束名未知）
            cur.execute(
                """
                DO $$
                DECLARE r RECORD;
                BEGIN
                  FOR r IN
                    SELECT n.nspname, t.relname, c.conname
                      FROM pg_constraint c
                      JOIN pg_class     t ON t.oid = c.conrelid
                      JOIN pg_namespace n ON n.oid = t.relnamespace
                     WHERE t.relname  = 'sys_users'
                       AND n.nspname  = current_schema()
                       AND c.contype  = 'c'
                       AND pg_get_constraintdef(c.oid) LIKE '%role%'
                  LOOP
                    EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I',
                                   r.nspname, r.relname, r.conname);
                  END LOOP;
                END $$;
                """
            )
            cur.execute(
                """ALTER TABLE sys_users
                     ADD CONSTRAINT sys_users_role_check
                     CHECK (role IN ('admin','user','technician'))"""
            )
        # 3) 初始化用户（存在 → 重置密码/角色/first_login）
        init_pw_hash = _hash_password(_INITIAL_PASSWORD)
        for username, real_name, role in _INITIAL_USERS:
            cur.execute("SELECT id FROM sys_users WHERE username = %s", (username,))
            if cur.fetchone() is None:
                cur.execute(
                    """INSERT INTO sys_users (username, password_hash, real_name, role, first_login)
                       VALUES (%s, %s, %s, %s, TRUE)""",
                    (username, init_pw_hash, real_name, role),
                )
            else:
                # 若初始用户已存在：始终重置为初始密码（12345678）+ 首次登录强制改密
                # （开发/启动时保证约定账户可用，避免被测试改密后遗忘。普通用户创建的
                #  非初始用户不受影响）
                cur.execute(
                    """UPDATE sys_users
                          SET password_hash = %s,
                              real_name     = %s,
                              role          = %s,
                              first_login   = TRUE,
                              is_active     = TRUE,
                              updated_at    = CURRENT_TIMESTAMP
                        WHERE username = %s""",
                    (init_pw_hash, real_name, role, username),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# 在启动时初始化用户表
try:
    _init_users()
    print("[auth] 用户表初始化完成")
except Exception as e:
    print(f"[auth] 用户表初始化警告: {e}")


# ---- 请求模型 ----
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)
    is_mobile: bool = False  # True=手机端登录（允许技术员登录）


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)


class ResetPasswordRequest(BaseModel):
    user_id: int
    new_password: str = Field(default=_INITIAL_PASSWORD, min_length=6, max_length=100)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    real_name: str = Field(..., min_length=1, max_length=50)
    role: str = Field(default="user", pattern=r"^(admin|user|technician)$")
    password: str = Field(default=_INITIAL_PASSWORD, min_length=6, max_length=100)


class DeleteUserRequest(BaseModel):
    user_id: int


# ---- FastAPI 依赖：从 Authorization 头获取当前用户 ----
from fastapi import Header as _Header, Depends as _Depends
from typing import Optional as _Opt


def _get_current_user(
    authorization: _Opt[str] = _Header(default=None),
) -> dict:
    """解析 Authorization: Bearer <token>，返回用户信息（id, username, role, real_name, first_login）。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ", 1)[1].strip()
    payload = _jwt_decode(token)
    if not payload or "uid" not in payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    import psycopg2 as _pg2
    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg2.connect(**conn_config)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, real_name, role, is_active, first_login "
            "FROM sys_users WHERE id = %s",
            (int(payload["uid"]),),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row[5]:  # is_active
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "real_name": row[3],
        "role": row[4],
        "is_active": row[5],
        "first_login": row[6],
    }


def _check_edit_permission(user: dict, owner: str | None, record_exists: bool = True) -> None:
    """编辑权限校验。

    record_exists=False：新建记录，任意登录用户可创建（归属在创建时写入）。
    record_exists=True：管理员可编辑全部；无归属（updated_by 为空）的记录仅管理员可编辑；
    否则仅本人（updated_by == 当前用户名）可编辑。
    """
    if user["role"] == "admin":
        return
    if not record_exists:
        return
    if not owner:
        raise HTTPException(status_code=403, detail="该记录暂无归属，仅管理员可编辑")
    if owner != user["username"]:
        raise HTTPException(status_code=403, detail="无权限编辑他人录入的数据")


def _user_from_row(row: tuple) -> dict:
    """把 sys_users 查询行安全转为 dict（排除 password_hash）。"""
    return {
        "id": row[0],
        "username": row[1],
        "real_name": row[3],
        "role": row[4],
        "is_active": row[5],
        "first_login": row[6],
        "created_at": str(row[7]) if len(row) > 7 else None,
        "updated_at": str(row[8]) if len(row) > 8 else None,
    }


def _get_admin(
    authorization: _Opt[str] = _Header(default=None),
) -> dict:
    user = _get_current_user(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def _detect_lan_ip() -> str:
    """检测本机局域网 IP 地址（用于二维码生成，手机扫码访问）"""
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
        # 连接到公共 DNS，操作系统会自动选择可用的网卡 IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# 缓存 LAN IP（服务器生命周期内不变）
_LAN_IP = _detect_lan_ip()

# 移动端采集密码（可通过环境变量 MOBILE_PASSWORD 配置）
import os as _os
_MOBILE_PASSWORD = _os.getenv("MOBILE_PASSWORD", "wheat123")


class PasswordVerifyRequest(BaseModel):
    password: str


# ============================================================
# 用户认证 API
# ============================================================
@app.post("/api/v1/auth/login")
async def api_login(req: LoginRequest):
    """登录：返回 token + 用户信息（不含 password_hash）。

    is_mobile=True  手机端登录（技术员允许）；
    is_mobile=False 电脑端登录（技术员角色被拒绝，需走手机端）。
    """
    import psycopg2 as _pg

    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, real_name, role, is_active, first_login "
            "FROM sys_users WHERE username = %s",
            (req.username.strip(),),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or not row[5]:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not _verify_password(req.password, row[2]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    role = row[4]
    # 技术员只能在手机端登录
    if role == "technician" and not req.is_mobile:
        raise HTTPException(
            status_code=403,
            detail="技术员账号仅限手机端登录使用，请在手机端登录（扫码进入）",
        )

    user_id = row[0]
    token = _jwt_b64({"uid": user_id, "sub": str(user_id)})
    return _success_response({
        "access_token": token,
        "token_type": "bearer",
        "user": _user_from_row(row),
    })


@app.get("/api/v1/auth/me")
async def api_get_me(authorization: _Opt[str] = _Header(default=None)):
    """获取当前登录用户信息（用于会话恢复）。"""
    user = _get_current_user(authorization)
    safe = dict(user)
    safe.pop("password_hash", None)
    return _success_response(safe)


@app.post("/api/v1/auth/change-password")
async def api_change_password(
    req: ChangePasswordRequest,
    authorization: _Opt[str] = _Header(default=None),
):
    """修改自己的密码。"""
    user = _get_current_user(authorization)
    if not _verify_password(req.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")
    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")

    new_hash = _hash_password(req.new_password)
    import psycopg2 as _pg

    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE sys_users SET password_hash = %s, first_login = FALSE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_hash, user["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    return _success_response(message="密码修改成功")


# ============================================================
# 用户管理 API（仅管理员可用）
# ============================================================
@app.get("/api/v1/admin/users")
async def api_admin_list_users(authorization: _Opt[str] = _Header(default=None)):
    """列出全部用户（密码哈希不返回）。"""
    _get_admin(authorization)
    import psycopg2 as _pg

    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, password_hash, real_name, role, is_active, first_login, created_at, updated_at "
            "FROM sys_users ORDER BY id"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return _success_response([_user_from_row(r) for r in rows])


@app.post("/api/v1/admin/users")
async def api_admin_create_user(
    req: CreateUserRequest,
    authorization: _Opt[str] = _Header(default=None),
):
    """创建用户（默认密码 12345678，首次登录强制修改）。"""
    _get_admin(authorization)
    import psycopg2 as _pg

    pw_hash = _hash_password(req.password)
    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    try:
        cur = conn.cursor()
        # 查重
        cur.execute("SELECT id FROM sys_users WHERE username = %s", (req.username.strip(),))
        if cur.fetchone() is not None:
            raise HTTPException(status_code=400, detail="用户名已存在")
        cur.execute(
            """INSERT INTO sys_users (username, password_hash, real_name, role, first_login)
               VALUES (%s, %s, %s, %s, TRUE) RETURNING *""",
            (req.username.strip(), pw_hash, req.real_name.strip(), req.role),
        )
        row = cur.fetchone()
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _success_response(_user_from_row(row), message="创建成功")


@app.post("/api/v1/admin/users/reset-password")
async def api_admin_reset_password(
    req: ResetPasswordRequest,
    authorization: _Opt[str] = _Header(default=None),
):
    """管理员重置普通用户密码（默认重置为 12345678，并开启首次登录强制修改）。"""
    admin = _get_admin(authorization)

    import psycopg2 as _pg

    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, role, username FROM sys_users WHERE id = %s", (req.user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        # 不能重置自己以外的管理员（安全规则：除非自己是管理员且目标为普通用户）
        if row[1] == "admin" and row[0] != admin["id"]:
            raise HTTPException(status_code=403, detail="不能重置其他管理员的密码")
        new_hash = _hash_password(req.new_password)
        cur.execute(
            "UPDATE sys_users SET password_hash = %s, first_login = TRUE, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (new_hash, req.user_id),
        )
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _success_response(message="密码已重置，用户首次登录需修改密码")


@app.delete("/api/v1/admin/users/{user_id}")
async def api_admin_delete_user(
    user_id: int,
    authorization: _Opt[str] = _Header(default=None),
):
    """删除用户。不能删除自己，不能删除仅剩的一个管理员。"""
    admin = _get_admin(authorization)
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")

    import psycopg2 as _pg

    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = _pg.connect(**conn_config)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, role FROM sys_users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if row[1] == "admin":
            cur.execute("SELECT COUNT(*) FROM sys_users WHERE role = 'admin' AND is_active = TRUE")
            cnt = cur.fetchone()[0]
            if cnt <= 1:
                raise HTTPException(status_code=400, detail="至少需要保留一个管理员")
        cur.execute("DELETE FROM sys_users WHERE id = %s", (user_id,))
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return _success_response(message="用户已删除")


@app.get("/api/v1/server-info")
async def get_server_info():
    """返回服务器信息（包括 LAN IP）供前端生成二维码"""
    return {
        "host": _LAN_IP,
        "port": 8001,
        "base_url": f"http://{_LAN_IP}:8001",
    }


@app.post("/api/v1/verify-password")
async def verify_password(req: PasswordVerifyRequest):
    """验证移动端采集密码"""
    if req.password != _MOBILE_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    return {"ok": True}


@app.get("/mobile_entry")
async def serve_mobile_entry(plot: str | None = None, plot_code: str | None = None, api: str | None = None):
    """移动端数据录入页面"""
    from fastapi.responses import FileResponse
    mobile_html = FRONTEND_DIR / "mobile_entry.html"
    if not mobile_html.exists():
        raise HTTPException(status_code=404, detail="移动端页面未找到")
    return FileResponse(str(mobile_html))


# 挂载静态前端服务（放在最后，确保 API 路由优先匹配）
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")






