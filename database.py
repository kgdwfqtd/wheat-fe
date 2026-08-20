# -*- coding: utf-8 -*-
"""PostgreSQL 数据库操作 — 建表 & CRUD（Repository 层）"""

import io
import zipfile
import logging
from datetime import datetime
from contextlib import contextmanager

import pandas as pd
import psycopg2
import psycopg2.extras

from config import DB_CONFIG, DB_BACKUP_MAX

logger = logging.getLogger(__name__)

# ---- 允许被 f-string 拼接的表名白名单 ----
_TABLE_WHITELIST = {
    "soil_data", "phenology", "emergence", "agronomic_traits",
    "physiological", "yield_data", "quality_data", "operation_log",
    "fertilization_log", "field_management",
    "plots", "experiment_bases",
}
# 重置时可按序清空的表（先子后父，避免 FK 冲突）
_RESET_ORDER = [
    "operation_log", "quality_data", "yield_data", "physiological",
    "agronomic_traits", "emergence", "phenology", "soil_data", "plots", "experiment_bases",
]


def _check_table(table: str):
    """防止 SQL 注入：只允许白名单内的表名"""
    if table not in _TABLE_WHITELIST:
        raise ValueError(f"非法的表名: {table}")


def _safe_result(fn, default=None):
    """轻量异常包装：捕获 psycopg2.Error 并记录日志"""
    def wrapper(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            return (True, result)
        except psycopg2.Error as e:
            logger.error("%s failed: %s", fn.__name__, e)
            return (False, str(e))
    return wrapper


# ============================================================
# 连接管理（上下文管理器，保证异常安全）
# ============================================================
@contextmanager
def get_conn():
    """获取 PostgreSQL 连接"""
    # 修复：确保 client_encoding 设置为 UTF8，避免中文字符解码错误
    conn_config = dict(DB_CONFIG)
    conn_config.setdefault("client_encoding", "UTF8")
    conn = psycopg2.connect(**conn_config)
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 试验基地管理
# ============================================================
def create_experiment_base(base_code: str, base_name: str, admin_code: str | None = None, address: str = '', latitude: float | None = None, longitude: float | None = None, remarks: str = ""):
    """创建试验基地。基地编号格式：6位行政区划代码 + 2位基地编号 + 年 + 月。"""
    if not base_code or len(base_code) < 10:
        raise ValueError("基地编号格式错误，至少应符合 6位行政区划 + 2位基地编号 + 年 + 月")
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO experiment_bases (base_code, base_name, admin_code, address, latitude, longitude, remarks, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (base_code) DO NOTHING
            """,
            (base_code, base_name, admin_code, address, latitude, longitude, remarks),
        )
    return base_code


def get_all_bases():
    """获取所有试验基地。"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM experiment_bases ORDER BY created_at DESC")
        rows = cur.fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_base_by_code(base_code: str):
    """按基地编号获取基地信息。"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM experiment_bases WHERE base_code = %s", (base_code,))
        row = cur.fetchone()
    return dict(row) if row else None


def update_experiment_base(base_code: str, base_name: str | None = None, admin_code: str | None = None, address: str | None = None, latitude: float | None = None, longitude: float | None = None, remarks: str | None = None):
    """更新试验基地信息。"""
    if not get_base_by_code(base_code):
        raise ValueError(f"基地 {base_code} 不存在")
    updates = []
    values = []
    if base_name is not None:
        updates.append("base_name = %s")
        values.append(base_name)
    if admin_code is not None:
        updates.append("admin_code = %s")
        values.append(admin_code)
    if address is not None:
        updates.append("address = %s")
        values.append(address)
    if latitude is not None:
        updates.append("latitude = %s")
        values.append(latitude)
    if longitude is not None:
        updates.append("longitude = %s")
        values.append(longitude)
    if remarks is not None:
        updates.append("remarks = %s")
        values.append(remarks)
    if not updates:
        return get_base_by_code(base_code)
    values.append(base_code)
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"UPDATE experiment_bases SET {', '.join(updates)} WHERE base_code = %s", values)
    return get_base_by_code(base_code)


def delete_experiment_base(base_code: str):
    """删除试验基地，并级联删除其下小区。"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM plots WHERE base_code = %s", (base_code,))
        cur.execute("DELETE FROM experiment_bases WHERE base_code = %s", (base_code,))
    return True


# ============================================================
# 建表
# ============================================================
def init_db():
    """初始化数据库表结构"""
    with get_conn() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS experiment_bases (
                id SERIAL PRIMARY KEY,
                base_code VARCHAR(30) UNIQUE NOT NULL,
                base_name VARCHAR(200) NOT NULL,
                admin_code VARCHAR(20) DEFAULT '',
                address VARCHAR(500) DEFAULT '',
                latitude DOUBLE PRECISION DEFAULT NULL,
                longitude DOUBLE PRECISION DEFAULT NULL,
                remarks TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 添加新字段（如果不存在）
        try:
            cur.execute("ALTER TABLE experiment_bases ADD COLUMN IF NOT EXISTS address VARCHAR(500) DEFAULT ''")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE experiment_bases ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION DEFAULT NULL")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE experiment_bases ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION DEFAULT NULL")
        except Exception:
            pass

        cur.execute("""
            CREATE TABLE IF NOT EXISTS plots (
                id SERIAL PRIMARY KEY,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                block VARCHAR(10) NOT NULL,
                treatment VARCHAR(20) NOT NULL,
                plot_code VARCHAR(30) NOT NULL,
                area_m2 DOUBLE PRECISION DEFAULT 20.0,
                field_name VARCHAR(100) DEFAULT ''
            )
        """)

        # 兼容旧表：清理残留的全局唯一约束 / 唯一索引，并按基地维度重建唯一性。
        stale_indexes = [
            "uq_plots_block_treatment",
            "plots_plot_code_key",
            "uq_plots_base_block_treatment",
            "uq_plots_base_plot_code",
        ]
        for index_name in stale_indexes:
            try:
                cur.execute(f'DROP INDEX IF EXISTS "{index_name}"')
            except Exception:
                conn.rollback()
                cur = conn.cursor()

        stale_constraints = [
            "uq_plots_block_treatment",
            "plots_plot_code_key",
            "uq_plots_base_block_treatment",
            "uq_plots_base_plot_code",
        ]
        for constraint_name in stale_constraints:
            try:
                cur.execute(f'ALTER TABLE plots DROP CONSTRAINT IF EXISTS "{constraint_name}"')
            except Exception:
                conn.rollback()
                cur = conn.cursor()

        try:
            cur.execute("ALTER TABLE plots ADD COLUMN IF NOT EXISTS base_code VARCHAR(30) NOT NULL DEFAULT '000000000000'")
        except Exception:
            conn.rollback()
            cur = conn.cursor()

        # 旧数据中可能存在多基地重复区组/处理编号或 plot_code，必须先清理后再建唯一索引。
        try:
            cur.execute("""
                DELETE FROM plots
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY base_code, block, treatment
                                   ORDER BY id
                               ) AS rn
                        FROM plots
                    ) s
                    WHERE rn > 1
                )
            """)
        except Exception:
            conn.rollback()
            cur = conn.cursor()
        try:
            # 唯一约束是 (base_code, plot_code)：不同基地允许相同编号，去重必须按基地维度
            cur.execute("""
                DELETE FROM plots
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id,
                               ROW_NUMBER() OVER (
                                   PARTITION BY base_code, plot_code
                                   ORDER BY id
                               ) AS rn
                        FROM plots
                    ) s
                    WHERE rn > 1
                )
            """)
        except Exception:
            conn.rollback()
            cur = conn.cursor()

        cur.execute("CREATE INDEX IF NOT EXISTS idx_plots_base_code ON plots(base_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_experiment_bases_code ON experiment_bases(base_code)")

        # 扩展 plots 表：播种与试验设计元数据（关键：品种、前茬、播种参数）
        for col_def in [
            "variety VARCHAR(100) DEFAULT ''",                  # 品种名称(如 郑麦9023)
            "previous_crop VARCHAR(50) DEFAULT ''",             # 前茬作物(玉米/大豆/水稻...)
            "soil_type VARCHAR(50) DEFAULT ''",                 # 土壤类型(潮土/褐土/砂姜黑土)
            "sowing_date DATE",                                 # 播种日期
            "sowing_rate DOUBLE PRECISION",                     # 播种量(kg/亩)
            "row_spacing DOUBLE PRECISION",                     # 行距(cm)
            "sowing_depth DOUBLE PRECISION",                    # 播深(cm)
            "sowing_method VARCHAR(20) DEFAULT ''",             # 播种方式(机播/撒播/条播)
            "plot_orientation VARCHAR(20) DEFAULT ''",          # 小区走向(南北/东西)
            "replication INTEGER",                              # 重复数(显式记录,目前靠block推断)
            "experiment_year INTEGER",                          # 试验年份(支持多年数据)
        ]:
            try:
                cur.execute(f"ALTER TABLE plots ADD COLUMN IF NOT EXISTS {col_def}")
            except Exception:
                pass
        
        # 创建天气数据表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS weather_data (
                id SERIAL PRIMARY KEY,
                base_code VARCHAR(30) NOT NULL,
                record_date DATE NOT NULL,
                temperature DOUBLE PRECISION,
                temperature_max DOUBLE PRECISION,
                temperature_min DOUBLE PRECISION,
                apparent_temperature DOUBLE PRECISION,
                humidity DOUBLE PRECISION,
                precipitation DOUBLE PRECISION,
                precipitation_probability DOUBLE PRECISION,
                wind_speed DOUBLE PRECISION,
                wind_direction DOUBLE PRECISION,
                wind_gust DOUBLE PRECISION,
                weather_code INTEGER,
                weather_description VARCHAR(100),
                is_day BOOLEAN DEFAULT TRUE,
                UNIQUE(base_code, record_date)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_weather_base_date ON weather_data(base_code, record_date)")

        # 创建 soil_data 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS soil_data (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                phase VARCHAR(10) NOT NULL CHECK(phase IN ('播前','收获后')),
                ph DOUBLE PRECISION,
                fe_available DOUBLE PRECISION,
                fe_total DOUBLE PRECISION,
                organic_matter DOUBLE PRECISION,
                p_available DOUBLE PRECISION,
                k_available DOUBLE PRECISION,
                cec DOUBLE PRECISION,
                bulk_density DOUBLE PRECISION,
                UNIQUE(plot_id, phase)
            )
        """)
        
        # 创建 phenology 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phenology (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                sowing VARCHAR(20),
                emergence VARCHAR(20),
                tillering VARCHAR(20),
                overwinter VARCHAR(20),
                regreening VARCHAR(20),
                jointing VARCHAR(20),
                heading VARCHAR(20),
                flowering VARCHAR(20),
                filling VARCHAR(20),
                maturity VARCHAR(20)
            )
        """)
        
        # 创建 emergence 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergence (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                seeds_sown INTEGER,
                emerged_7d INTEGER,
                rate_7d DOUBLE PRECISION,
                emerged_14d INTEGER,
                rate_14d DOUBLE PRECISION,
                basic_seedlings DOUBLE PRECISION
            )
        """)
        
        # 创建 agronomic_traits 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agronomic_traits (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                tillers_prewinter DOUBLE PRECISION,
                tillers_postregreen DOUBLE PRECISION,
                tillers_jointing DOUBLE PRECISION,
                plant_height DOUBLE PRECISION,
                lai_jointing DOUBLE PRECISION,
                lai_heading DOUBLE PRECISION,
                dry_weight_jointing DOUBLE PRECISION,
                dry_weight_heading DOUBLE PRECISION,
                dry_weight_maturity DOUBLE PRECISION,
                root_dry_weight DOUBLE PRECISION
            )
        """)
        
        # 创建 physiological 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS physiological (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                spad_jointing DOUBLE PRECISION,
                spad_heading DOUBLE PRECISION,
                spad_filling DOUBLE PRECISION,
                photo_rate_heading DOUBLE PRECISION,
                photo_rate_filling DOUBLE PRECISION,
                active_fe_jointing DOUBLE PRECISION,
                active_fe_filling DOUBLE PRECISION,
                cat DOUBLE PRECISION,
                pod DOUBLE PRECISION
            )
        """)
        
        # 创建 yield_data 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS yield_data (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                spikes_per_mu DOUBLE PRECISION,
                grains_per_spike DOUBLE PRECISION,
                thousand_grain_wt_1 DOUBLE PRECISION,
                thousand_grain_wt_2 DOUBLE PRECISION,
                theoretical_yield DOUBLE PRECISION,
                actual_yield DOUBLE PRECISION,
                harvest_index DOUBLE PRECISION
            )
        """)
        
        # 创建 quality_data 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quality_data (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                grain_protein DOUBLE PRECISION,
                wet_gluten DOUBLE PRECISION,
                sds_sedimentation DOUBLE PRECISION,
                grain_fe DOUBLE PRECISION,
                flour_fe DOUBLE PRECISION
            )
        """)
        
        # 创建 operation_log 表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operation_log (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER REFERENCES plots(id) ON DELETE SET NULL,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                date VARCHAR(20) NOT NULL,
                time VARCHAR(10),
                op_type VARCHAR(50) NOT NULL,
                treatment VARCHAR(20),
                block VARCHAR(10),
                dosage VARCHAR(200),
                weather VARCHAR(20),
                temperature DOUBLE PRECISION,
                humidity DOUBLE PRECISION,
                operator VARCHAR(50),
                remarks TEXT
            )
        """)
        
        # 创建索引以提高查询性能
        for tbl in [
            "soil_data", "phenology", "emergence", "agronomic_traits",
            "physiological", "yield_data", "quality_data", "operation_log",
        ]:
            cur.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS base_code VARCHAR(30) NOT NULL DEFAULT '000000000000'")

        # ============================================================
        # 新增表：铁肥施用记录 fertilization_log
        # 核心目的：结构化记录每次铁肥施用方法，为"使用方法优化"提供输入变量
        # ============================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fertilization_log (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                application_date DATE NOT NULL,
                growth_stage VARCHAR(20) DEFAULT '',
                fertilizer_type VARCHAR(50) NOT NULL,
                application_method VARCHAR(30) DEFAULT '',
                concentration DOUBLE PRECISION,
                dilution_ratio DOUBLE PRECISION,
                dose_per_plot DOUBLE PRECISION,
                dose_per_mu DOUBLE PRECISION,
                active_iron_amount DOUBLE PRECISION,
                spray_volume DOUBLE PRECISION,
                application_times INTEGER DEFAULT 1,
                operator VARCHAR(50) DEFAULT '',
                weather_temp DOUBLE PRECISION,
                weather_humidity DOUBLE PRECISION,
                remarks TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fert_log_plot ON fertilization_log(plot_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fert_log_date ON fertilization_log(application_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_fert_log_base ON fertilization_log(base_code)")

        # ============================================================
        # 新增表：田间管理记录 field_management
        # 记录灌溉/除草/植保/常规施肥等非铁肥管理操作
        # ============================================================
        cur.execute("""
            CREATE TABLE IF NOT EXISTS field_management (
                id SERIAL PRIMARY KEY,
                plot_id INTEGER REFERENCES plots(id) ON DELETE SET NULL,
                base_code VARCHAR(30) NOT NULL DEFAULT '000000000000',
                management_date DATE NOT NULL,
                management_type VARCHAR(30) NOT NULL,
                input_name VARCHAR(100) DEFAULT '',
                input_amount DOUBLE PRECISION,
                input_unit VARCHAR(20) DEFAULT '',
                method VARCHAR(30) DEFAULT '',
                operator VARCHAR(50) DEFAULT '',
                remarks TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_field_mgmt_plot ON field_management(plot_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_field_mgmt_date ON field_management(management_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_field_mgmt_base ON field_management(base_code)")

        # ============================================================
        # 采样表统一增加 sampling_date、sampler 字段（支持时序分析）
        # ============================================================
        sampling_tables = ["soil_data", "agronomic_traits", "physiological", "yield_data", "quality_data"]
        for tbl in sampling_tables:
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS sampling_date DATE")
            except Exception:
                pass
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS sampler VARCHAR(50) DEFAULT ''")
            except Exception:
                pass
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS sampling_method VARCHAR(50) DEFAULT ''")
            except Exception:
                pass

        # 产量表额外增加：收获日期、实收面积、含水率、标准产量
        for col_def in [
            "harvest_date DATE",
            "harvest_area DOUBLE PRECISION",
            "moisture_content DOUBLE PRECISION",
            "standardized_yield DOUBLE PRECISION",
        ]:
            try:
                cur.execute(f"ALTER TABLE yield_data ADD COLUMN IF NOT EXISTS {col_def}")
            except Exception:
                pass

        cur.execute("DROP INDEX IF EXISTS uq_plots_base_block_treatment")
        cur.execute("DROP INDEX IF EXISTS uq_plots_base_plot_code")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_plots_base_block_treatment ON plots(base_code, block, treatment)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_plots_base_plot_code ON plots(base_code, plot_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plots_block_treatment ON plots(block, treatment)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plots_plot_code ON plots(plot_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plots_base_code ON plots(base_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_soil_data_plot_id ON soil_data(plot_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_operation_log_date ON operation_log(date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_operation_log_base_code ON operation_log(base_code)")

        # 数据表统一增加录入归属与时间戳列（幂等），支撑「数据查看」的录入人归属与编辑权限。
        # 归属 = 最后保存者（updated_by），首次保存时同时记入 created_by。
        _owner_cols = [
            "created_by VARCHAR(50) DEFAULT ''",
            "updated_by VARCHAR(50) DEFAULT ''",
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ]
        _owner_tables = [
            "soil_data", "phenology", "emergence", "agronomic_traits",
            "physiological", "yield_data", "quality_data", "operation_log",
            "fertilization_log", "field_management",
        ]
        for tbl in _owner_tables:
            for col_def in _owner_cols:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col_def}")


# ============================================================
# 小区 CRUD
# ============================================================
def init_plots(field_name="", base_code: str | None = None):
    """初始化 18 个小区。默认需要指向一个试验基地，兼容旧调用。"""
    from utils import BLOCKS, TREATMENT_CODES, make_plot_code

    target_base = base_code or "000000000000"
    if not get_base_by_code(target_base):
        create_experiment_base(
            base_code=target_base,
            base_name="默认试验基地",
            admin_code="000000",
            remarks="兼容旧数据，默认唯一基地",
        )

    created = 0
    with get_conn() as conn:
        cur = conn.cursor()
        for block in BLOCKS:
            for trt in TREATMENT_CODES:
                code = make_plot_code(block, trt)
                cur.execute(
                    "INSERT INTO plots (base_code, block, treatment, plot_code, field_name) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (base_code, block, treatment) DO NOTHING",
                    (target_base, block, trt, code, field_name),
                )
                if cur.rowcount > 0:
                    created += 1
    return created


def get_all_plots(base_code: str | None = None):
    """获取所有小区数据，可按基地过滤。"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if base_code:
            cur.execute("SELECT * FROM plots WHERE base_code = %s ORDER BY block, treatment", (base_code,))
        else:
            cur.execute("SELECT * FROM plots ORDER BY base_code, block, treatment")
        rows = cur.fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_plot_by_code(plot_code, base_code=None):
    """根据小区编号获取小区信息。

    多基地存在相同 plot_code，传入 base_code 时按 (base_code, plot_code) 精确匹配；
    缺省保持旧行为（按 plot_code 取第一条）。
    """
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if base_code:
            cur.execute("SELECT * FROM plots WHERE base_code = %s AND plot_code = %s",
                        (base_code, plot_code))
        else:
            cur.execute("SELECT * FROM plots WHERE plot_code = %s", (plot_code,))
        row = cur.fetchone()
    return dict(row) if row else None


def get_plots_by_base(base_code: str):
    """按基地编号获取小区列表。"""
    return get_all_plots(base_code=base_code)


# ============================================================
# 重置所有数据
# ============================================================
def reset_all_data():
    """清空所有数据表，并重新初始化小区。"""
    with get_conn() as conn:
        cur = conn.cursor()
        for tbl in _RESET_ORDER:
            _check_table(tbl)
            cur.execute(f"DELETE FROM {tbl}")
    init_plots(base_code="000000000000")
    logger.warning("All data reset — plots re-initialized.")


# ============================================================
# 通用 CRUD（支持复合键）
# ============================================================
def upsert_record(table: str, plot_id: int, data_dict: dict, extra_keys: dict | None = None,
                  created_by: str | None = None, updated_by: str | None = None):
    """插入或更新记录。

    created_by / updated_by 用于记录归属（数据查看的编辑权限依据 = updated_by，即最后保存者）。
    """
    _check_table(table)
    if not data_dict:
        return

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT base_code FROM plots WHERE id = %s", (plot_id,))
        plot_row = cur.fetchone()
        plot_base_code = plot_row[0] if plot_row and plot_row[0] else "000000000000"
        payload = dict(data_dict)
        if "base_code" not in payload or not payload.get("base_code"):
            payload["base_code"] = plot_base_code

        where_clause = "plot_id = %s"
        where_vals = [plot_id]
        if extra_keys:
            for k, v in extra_keys.items():
                where_clause += f" AND {k}=%s"
                where_vals.append(v)

        cur.execute(f"SELECT id FROM {table} WHERE {where_clause}", where_vals)
        existing = cur.fetchone()

        if existing:
            sets = ", ".join(f"{k}=%s" for k in payload.keys())
            vals = list(payload.values())
            if updated_by:
                sets += ", updated_by=%s"
                vals.append(updated_by)
            sets += ", updated_at=CURRENT_TIMESTAMP"
            # 占位符顺序 = SET 列 在前、WHERE 条件 在后，vals 必须按同一顺序拼接
            vals += where_vals
            cur.execute(f"UPDATE {table} SET {sets} WHERE {where_clause}", vals)
        else:
            cols = ["plot_id"]
            if extra_keys:
                cols.extend(extra_keys.keys())
            cols.extend(payload.keys())
            if created_by:
                cols.append("created_by")
                payload["created_by"] = created_by
            if updated_by:
                cols.append("updated_by")
                payload["updated_by"] = updated_by
            placeholders = ", ".join(["%s" for _ in cols])
            vals = where_vals + list(payload.values())
            cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", vals)


def get_record_owner(table: str, plot_id: int, extra_keys: dict | None = None) -> str | None:
    """返回某小区已有记录的 updated_by（归属人），不存在返回 None。用于写前权限判断。"""
    _check_table(table)
    with get_conn() as conn:
        cur = conn.cursor()
        where_clause = "plot_id = %s"
        vals = [plot_id]
        if extra_keys:
            for k, v in extra_keys.items():
                where_clause += f" AND {k}=%s"
                vals.append(v)
        cur.execute(f"SELECT updated_by FROM {table} WHERE {where_clause}", vals)
        row = cur.fetchone()
    if not row:
        return None  # 无记录（调用方视为「新建」）
    return row[0] if row[0] is not None else ""  # 有记录但无归属 → 空串（仅管理员可编辑）


def get_record_by_id(table: str, record_id: int) -> dict | None:
    """按主键 id 读取一条记录（含 updated_by 归属），不存在返回 None。"""
    _check_table(table)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"SELECT * FROM {table} WHERE id = %s", (int(record_id),))
        row = cur.fetchone()
    return dict(row) if row else None


def update_record_by_id(table: str, record_id: int, data_dict: dict, updated_by: str | None = None):
    """按主键 id 更新记录的指定字段，并写入 updated_by / updated_at。"""
    _check_table(table)
    if not data_dict:
        return
    with get_conn() as conn:
        cur = conn.cursor()
        sets = ", ".join(f"{k}=%s" for k in data_dict.keys())
        vals = list(data_dict.values())
        if updated_by:
            sets += ", updated_by=%s"
            vals.append(updated_by)
        sets += ", updated_at=CURRENT_TIMESTAMP"
        vals.append(int(record_id))
        cur.execute(f"UPDATE {table} SET {sets} WHERE id = %s", vals)


def query_data_view(table: str, base_code: str | None = None):
    """返回某数据表的记录，附带小区信息（LEFT JOIN，plot_id 为空的记录小区回显为「全基地」）。

    供「数据查看」页聚合查询使用；包含 created_by/updated_by/updated_at 归属列。
    """
    _check_table(table)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        sql = f"""
            SELECT p.base_code AS plot_base_code, p.plot_code, p.block, p.treatment, t.*
            FROM {table} t
            LEFT JOIN plots p ON t.plot_id = p.id
        """
        vals: list = []
        if base_code:
            sql += " WHERE t.base_code = %s"
            vals.append(base_code)
        sql += " ORDER BY t.id"
        cur.execute(sql, vals)
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        # 无小区归属（如全基地操作日志）时回显
        if d.get("plot_code") is None:
            d["plot_code"] = "全基地"
        out.append(d)
    return out


def get_record(table: str, plot_id: int, extra_keys: dict | None = None):
    """读取记录"""
    _check_table(table)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        where_clause = "plot_id = %s"
        vals = [plot_id]
        if extra_keys:
            for k, v in extra_keys.items():
                where_clause += f" AND {k}=%s"
                vals.append(v)
        cur.execute(f"SELECT * FROM {table} WHERE {where_clause}", vals)
        row = cur.fetchone()
    return dict(row) if row else None


def get_all_records(table: str, as_dataframe=True):
    """读取某表全部记录（JOIN plots）"""
    _check_table(table)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(f"""
            SELECT p.plot_code, p.block, p.treatment, t.*
            FROM {table} t
            JOIN plots p ON t.plot_id = p.id
            ORDER BY p.block, p.treatment
        """)
        rows = cur.fetchall()
        if as_dataframe:
            df = pd.DataFrame([dict(r) for r in rows])
            # 修复：手动将 NaN 值转换为 None，便于 JSON 序列化
            if not df.empty:
                # 创建一个副本进行处理
                fixed_records = []
                for _, row in df.iterrows():
                    record = {}
                    for col in df.columns:
                        val = row[col]
                        if pd.isna(val):
                            record[col] = None
                        else:
                            record[col] = val
                    fixed_records.append(record)
                df = pd.DataFrame(fixed_records)
            return df
        else:
            # 修复：将 NaN 转换为 None
            result = []
            for r in rows:
                d = dict(r)
                for k, v in d.items():
                    if isinstance(v, float) and (pd.isna(v) or v != v):
                        d[k] = None
                result.append(d)
            return result


# ============================================================
# 操作日志 CRUD
# ============================================================
def add_operation(date, op_type, treatment="", block="", time="",
                   dosage="", weather="", temperature=None, humidity=None,
                   operator="", remarks="", plot_id=None, base_code=None,
                   created_by=None, updated_by=None):
    """添加操作日志"""
    if not base_code and plot_id is not None:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT base_code FROM plots WHERE id = %s", (plot_id,))
            row = cur.fetchone()
            if row and row[0]:
                base_code = row[0]
    base_code = base_code or "000000000000"

    owner_by = updated_by or created_by
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO operation_log (plot_id, base_code, date, time, op_type, treatment, block,
                                       dosage, weather, temperature, humidity, operator, remarks,
                                       created_by, updated_by, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
        """, (plot_id, base_code, date, time, op_type, treatment, block,
              dosage, weather, temperature, humidity, operator, remarks,
              owner_by, owner_by))


def get_operations(limit=50):
    """获取操作日志"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, base_code, date, time, op_type, treatment, block, dosage,
                   weather, temperature, humidity, operator, remarks
            FROM operation_log
            ORDER BY date DESC, time DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    return pd.DataFrame([dict(r) for r in rows])


# ============================================================
# 数据完整性统计
# ============================================================
def get_completion_stats():
    """返回各表的数据录入完成度。"""
    tables_1to1 = ["phenology", "emergence", "agronomic_traits",
                   "physiological", "yield_data", "quality_data"]
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM plots")
        total_plots = cur.fetchone()[0]
        stats = {}

        if total_plots:
            cur.execute("SELECT COUNT(DISTINCT plot_id) FROM soil_data WHERE phase='播前'")
            cnt_soil_pre = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT plot_id) FROM soil_data WHERE phase='收获后'")
            cnt_soil_post = cur.fetchone()[0]
            stats["soil_data"] = {
                "filled": cnt_soil_pre + cnt_soil_post,
                "total": total_plots,
                "pct_pre": round(cnt_soil_pre / total_plots * 100, 1),
                "pct_post": round(cnt_soil_post / total_plots * 100, 1),
                "pct": round((cnt_soil_pre + cnt_soil_post) / (total_plots * 2) * 100, 1),
            }
        else:
            stats["soil_data"] = {"filled": "0/0", "total": 0, "pct": 0, "pct_pre": 0, "pct_post": 0}

        for tbl in tables_1to1:
            _check_table(tbl)
            cur.execute(f"SELECT COUNT(DISTINCT plot_id) FROM {tbl}")
            cnt = cur.fetchone()[0]
            stats[tbl] = {
                "filled": cnt, "total": total_plots,
                "pct": round(cnt / total_plots * 100, 1) if total_plots else 0,
            }

        cur.execute("SELECT COUNT(*) FROM operation_log")
        stats["operation_log"] = {
            "filled": cur.fetchone()[0],
            "total": "-", "pct": "-",
        }
    return stats


# ============================================================
# 仪表盘矩阵
# ============================================================
def get_treatment_table_matrix():
    """返回处理 × 数据表完成度矩阵（百分比，0-100 整数）。

    1:1 数据表（物候/出苗/农艺/生理/产量/品质）：按 已录小区数 / 该处理小区总数 计；
    土壤数据：播前 + 收获后 两条记录，按 已录记录数 / (该处理小区总数 × 2) 计。
    """
    tables_1to1 = ["phenology", "emergence", "agronomic_traits",
                   "physiological", "yield_data", "quality_data"]
    from utils import TREATMENT_CODES

    with get_conn() as conn:
        cur = conn.cursor()
        result: dict[str, dict[str, int]] = {trt: {} for trt in TREATMENT_CODES}

        # 每个处理的小区总数（一次查询）
        cur.execute("SELECT treatment, COUNT(*) AS total FROM plots GROUP BY treatment")
        total_map = {r[0]: r[1] for r in cur.fetchall()}

        for tbl in tables_1to1:
            _check_table(tbl)
            cur.execute(f"""
                SELECT p.treatment, COUNT(DISTINCT t.plot_id) AS cnt
                FROM plots p
                LEFT JOIN {tbl} t ON p.id = t.plot_id
                GROUP BY p.treatment
            """)
            cnt_map = {r[0]: r[1] for r in cur.fetchall()}
            for trt in TREATMENT_CODES:
                total = total_map.get(trt, 0)
                cnt = cnt_map.get(trt, 0)
                result[trt][tbl] = round(cnt / total * 100) if total else 0

        # 土壤：区分播前 / 收获后，共两个阶段
        cur.execute("""
            SELECT p.treatment,
                   COUNT(DISTINCT t.plot_id) FILTER (WHERE t.phase = '播前') AS pre,
                   COUNT(DISTINCT t.plot_id) FILTER (WHERE t.phase = '收获后') AS post
            FROM plots p
            LEFT JOIN soil_data t ON p.id = t.plot_id
            GROUP BY p.treatment
        """)
        soil_map = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        for trt in TREATMENT_CODES:
            total = total_map.get(trt, 0)
            pre, post = soil_map.get(trt, (0, 0))
            result[trt]["soil_data"] = round((pre + post) / (total * 2) * 100) if total else 0

    return result


# ============================================================
# Excel 导出
# ============================================================
def export_to_excel(filepath_or_buffer, base_code: str | None = None):
    """导出所有数据到 Excel（支持路径字符串或 BytesIO，可按基地筛选）"""
    table_names = {
        "plots": "小区信息", "soil_data": "土壤数据",
        "phenology": "物候期", "emergence": "出苗调查",
        "agronomic_traits": "农艺性状", "physiological": "生理指标",
        "yield_data": "产量数据", "quality_data": "品质数据",
        "operation_log": "操作日志",
    }
    with pd.ExcelWriter(filepath_or_buffer, engine="openpyxl") as writer:
        summary_data = []
        for tbl, sheet_name in table_names.items():
            df = get_all_records(tbl)
            if base_code and "base_code" in df.columns:
                df = df[df["base_code"] == base_code]
            if df is not None and not df.empty:
                id_cols = [c for c in df.columns if c == 'id' or c == 'plot_id']
                df_out = df.drop(columns=[c for c in id_cols if c in df.columns], errors='ignore')
                df_out.to_excel(writer, sheet_name=sheet_name, index=False)
                summary_data.append({"数据表": sheet_name, "记录数": len(df)})
            else:
                summary_data.append({"数据表": sheet_name, "记录数": 0})
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="数据概览", index=False)
    return filepath_or_buffer


# ============================================================
# 备份（简化版，使用 pg_dump）
# ============================================================
def backup_db():
    """自动备份数据库"""
    import subprocess
    import os
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"backup_{ts}.sql")
    
    # 使用 pg_dump 备份
    cmd = f'pg_dump -h {os.getenv("POSTGRES_HOST", "localhost")} -p {os.getenv("POSTGRES_PORT", "5432")} -U {os.getenv("POSTGRES_USER", "postgres")} -d {os.getenv("POSTGRES_DB", "wheat_fe")} -f "{bak_path}"'
    
    try:
        # 设置 PGPASSWORD 环境变量
        env = os.environ.copy()
        env["PGPASSWORD"] = os.getenv("POSTGRES_PASSWORD", "20251219")
        
        result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Backup created: %s", bak_path)
            return bak_path
        else:
            logger.error("Backup failed: %s", result.stderr)
            return None
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return None


# ============================================================
# 启动时初始化
# ============================================================
# ============================================================
# 天气数据操作函数
# ============================================================
def save_weather_data(base_code: str, record_date, weather_data: dict):
    """保存天气数据。"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO weather_data (
                base_code, record_date, temperature, temperature_max, temperature_min,
                apparent_temperature, humidity, precipitation, precipitation_probability,
                wind_speed, wind_direction, wind_gust, weather_code, weather_description, is_day
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (base_code, record_date) DO UPDATE SET
                temperature = EXCLUDED.temperature,
                temperature_max = EXCLUDED.temperature_max,
                temperature_min = EXCLUDED.temperature_min,
                apparent_temperature = EXCLUDED.apparent_temperature,
                humidity = EXCLUDED.humidity,
                precipitation = EXCLUDED.precipitation,
                precipitation_probability = EXCLUDED.precipitation_probability,
                wind_speed = EXCLUDED.wind_speed,
                wind_direction = EXCLUDED.wind_direction,
                wind_gust = EXCLUDED.wind_gust,
                weather_code = EXCLUDED.weather_code,
                weather_description = EXCLUDED.weather_description,
                is_day = EXCLUDED.is_day
            """,
            (
                base_code, record_date,
                weather_data.get('temperature'),
                weather_data.get('temperature_max'),
                weather_data.get('temperature_min'),
                weather_data.get('apparent_temperature'),
                weather_data.get('humidity'),
                weather_data.get('precipitation'),
                weather_data.get('precipitation_probability'),
                weather_data.get('wind_speed'),
                weather_data.get('wind_direction'),
                weather_data.get('wind_gust'),
                weather_data.get('weather_code'),
                weather_data.get('weather_description'),
                weather_data.get('is_day', True),
            ),
        )
    return True


def get_weather_data(base_code: str, start_date=None, end_date=None):
    """获取基地天气数据。"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if start_date and end_date:
            cur.execute(
                "SELECT * FROM weather_data WHERE base_code = %s AND record_date BETWEEN %s AND %s ORDER BY record_date DESC",
                (base_code, start_date, end_date)
            )
        else:
            cur.execute(
                "SELECT * FROM weather_data WHERE base_code = %s ORDER BY record_date DESC",
                (base_code,)
            )
        rows = cur.fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def get_latest_weather(base_code: str):
    """获取基地最新的天气数据。"""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM weather_data WHERE base_code = %s ORDER BY record_date DESC LIMIT 1",
            (base_code,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def delete_weather_data(base_code: str, record_date=None):
    """删除基地天气数据。"""
    with get_conn() as conn:
        cur = conn.cursor()
        if record_date:
            cur.execute("DELETE FROM weather_data WHERE base_code = %s AND record_date = %s", (base_code, record_date))
        else:
            cur.execute("DELETE FROM weather_data WHERE base_code = %s", (base_code,))
    return True


# ============================================================
# 启动时初始化
# ============================================================
if __name__ == "__main__":
    init_db()
    init_plots()
    print("Database initialized.")


