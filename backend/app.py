# -*- coding: utf-8 -*-
"""FastAPI 后端入口：真正的前后端分离 API。"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
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
    get_treatment_table_matrix,
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
    data: dict[str, Any] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


def _get_plot_id(plot_code: str) -> int:
    plot = get_plot_by_code(plot_code)
    if plot is None:
        raise HTTPException(status_code=404, detail=f"小区 {plot_code} 不存在")
    return int(plot["id"])


def _validate_base_code(base_code: str) -> str:
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
    _validate_base_code(base_code)
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
    existing = get_plot_by_code(plot_code)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"小区 {plot_code} 已存在")

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
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
                    try:
                        cur.execute(
                            """
                            INSERT INTO plots (base_code, block, treatment, plot_code, area_m2)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (plot_code) DO NOTHING
                            """,
                            (base_code, block, treatment, plot_code, 20.0),
                        )
                        created += 1
                    except Exception:
                        pass
    
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
    existing = get_plot_by_code(plot_code)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"小区 {plot_code} 不存在")

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
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
                    payload.plot_code or plot_code,
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
                    int(existing["id"]),
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
async def create_fertilization_log(payload: FertilizationLogRequest):
    """新增铁肥施用记录。"""
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
                    application_times, operator, weather_temp, weather_humidity, remarks)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (plot_id, base_code, payload.application_date, payload.growth_stage,
                 payload.fertilizer_type, payload.application_method, payload.concentration,
                 payload.dilution_ratio, payload.dose_per_plot, payload.dose_per_mu,
                 payload.active_iron_amount, payload.spray_volume, payload.application_times,
                 payload.operator, payload.weather_temp, payload.weather_humidity, payload.remarks),
            )
            new_id = cur.fetchone()[0]
    return _success_response({"id": new_id}, message="fertilization log created")


@app.put("/api/v1/fertilization/{log_id}")
async def update_fertilization_log(log_id: int, payload: FertilizationLogRequest):
    """更新铁肥施用记录。"""
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
                    operator=%s, weather_temp=%s, weather_humidity=%s, remarks=%s
                WHERE id=%s
                """,
                (plot_id, base_code, payload.application_date, payload.growth_stage,
                 payload.fertilizer_type, payload.application_method, payload.concentration,
                 payload.dilution_ratio, payload.dose_per_plot, payload.dose_per_mu,
                 payload.active_iron_amount, payload.spray_volume, payload.application_times,
                 payload.operator, payload.weather_temp, payload.weather_humidity, payload.remarks, log_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"施用记录 {log_id} 不存在")
    return _success_response({"id": log_id}, message="fertilization log updated")


@app.delete("/api/v1/fertilization/{log_id}")
async def delete_fertilization_log(log_id: int):
    """删除铁肥施用记录。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fertilization_log WHERE id=%s", (log_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"施用记录 {log_id} 不存在")
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
async def create_field_management(payload: FieldManagementRequest):
    """新增田间管理记录。"""
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
                    input_name, input_amount, input_unit, method, operator, remarks)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (plot_id, base_code, payload.management_date, payload.management_type,
                 payload.input_name, payload.input_amount, payload.input_unit,
                 payload.method, payload.operator, payload.remarks),
            )
            new_id = cur.fetchone()[0]
    return _success_response({"id": new_id}, message="field management created")


@app.put("/api/v1/field-management/{log_id}")
async def update_field_management(log_id: int, payload: FieldManagementRequest):
    """更新田间管理记录。"""
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
                UPDATE field_management SET
                    plot_id=%s, base_code=%s, management_date=%s, management_type=%s,
                    input_name=%s, input_amount=%s, input_unit=%s, method=%s,
                    operator=%s, remarks=%s
                WHERE id=%s
                """,
                (plot_id, base_code, payload.management_date, payload.management_type,
                 payload.input_name, payload.input_amount, payload.input_unit,
                 payload.method, payload.operator, payload.remarks, log_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"管理记录 {log_id} 不存在")
    return _success_response({"id": log_id}, message="field management updated")


@app.delete("/api/v1/field-management/{log_id}")
async def delete_field_management(log_id: int):
    """删除田间管理记录。"""
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM field_management WHERE id=%s", (log_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"管理记录 {log_id} 不存在")
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
async def upsert_table_record(table_name: str, payload: TableRecordRequest):
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=404, detail=f"不支持的数据表: {table_name}")
    if not payload.data:
        raise HTTPException(status_code=400, detail="请求体缺少 data 字段或为空")

    if table_name == "operation_log":
        record = dict(payload.data)
        if payload.plot_code:
            record["plot_id"] = _get_plot_id(payload.plot_code)
        add_operation(**record)
        return _success_response({"table": table_name, "plot_code": payload.plot_code}, message="operation saved")

    if payload.plot_code is None:
        raise HTTPException(status_code=400, detail="该表需要提供 plot_code")

    plot_id = _get_plot_id(payload.plot_code)
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

    upsert_record(table_name, plot_id, data, extra_keys=dict(payload.extra) or None)
    return _success_response({"table": table_name, "plot_code": payload.plot_code}, message="record saved")


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


# 挂载静态前端服务（放在最后，确保 API 路由优先匹配）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")






