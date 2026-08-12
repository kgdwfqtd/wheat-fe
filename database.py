# -*- coding: utf-8 -*-
"""SQLite 数据库操作 — 建表 & CRUD（Repository 层）"""

import sqlite3
import os
import io
import shutil
import glob
import logging
from datetime import datetime
from contextlib import contextmanager

import pandas as pd

from config import DB_PATH, DB_BACKUP_MAX

logger = logging.getLogger(__name__)

# ---- 允许被 f-string 拼接的表名白名单 ----
_TABLE_WHITELIST = {
    "soil_data", "phenology", "emergence", "agronomic_traits",
    "physiological", "yield_data", "quality_data", "operation_log", "plots",
}
# 重置时可按序清空的表（先子后父，避免 FK 冲突）
_RESET_ORDER = [
    "operation_log", "quality_data", "yield_data", "physiological",
    "agronomic_traits", "emergence", "phenology", "soil_data", "plots",
]


def _check_table(table: str):
    """防止 SQL 注入：只允许白名单内的表名"""
    if table not in _TABLE_WHITELIST:
        raise ValueError(f"非法的表名: {table}")


def _safe_result(fn, default=None):
    """轻量异常包装：捕获 sqlite3.Error 并记录日志，返回 (ok, result_or_msg)"""
    def wrapper(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            return (True, result)
        except sqlite3.Error as e:
            logger.error("%s failed: %s", fn.__name__, e)
            return (False, str(e))
    return wrapper


# ============================================================
# 连接管理（上下文管理器，保证异常安全）
# ============================================================
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# 建表
# ============================================================
def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS plots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block TEXT NOT NULL,
                treatment TEXT NOT NULL,
                plot_code TEXT UNIQUE NOT NULL,
                area_m2 REAL DEFAULT 20.0,
                field_name TEXT DEFAULT '',
                UNIQUE(block, treatment)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS soil_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL REFERENCES plots(id) ON DELETE CASCADE,
                phase TEXT NOT NULL CHECK(phase IN ('播前','收获后')),
                ph REAL, fe_available REAL, fe_total REAL,
                organic_matter REAL, p_available REAL, k_available REAL,
                cec REAL, bulk_density REAL,
                UNIQUE(plot_id, phase)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS phenology (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                sowing TEXT, emergence TEXT, tillering TEXT,
                overwinter TEXT, regreening TEXT, jointing TEXT,
                heading TEXT, flowering TEXT, filling TEXT, maturity TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                seeds_sown INTEGER, emerged_7d INTEGER, rate_7d REAL,
                emerged_14d INTEGER, rate_14d REAL, basic_seedlings REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agronomic_traits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                tillers_prewinter REAL, tillers_postregreen REAL,
                tillers_jointing REAL, plant_height REAL,
                lai_jointing REAL, lai_heading REAL,
                dry_weight_jointing REAL, dry_weight_heading REAL,
                dry_weight_maturity REAL, root_dry_weight REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS physiological (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                spad_jointing REAL, spad_heading REAL, spad_filling REAL,
                photo_rate_heading REAL, photo_rate_filling REAL,
                active_fe_jointing REAL, active_fe_filling REAL,
                cat REAL, pod REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS yield_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                spikes_per_mu REAL, grains_per_spike REAL,
                thousand_grain_wt_1 REAL, thousand_grain_wt_2 REAL,
                theoretical_yield REAL, actual_yield REAL, harvest_index REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quality_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER NOT NULL UNIQUE REFERENCES plots(id) ON DELETE CASCADE,
                grain_protein REAL, wet_gluten REAL,
                sds_sedimentation REAL, grain_fe REAL, flour_fe REAL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plot_id INTEGER REFERENCES plots(id) ON DELETE SET NULL,
                date TEXT NOT NULL, time TEXT, op_type TEXT NOT NULL,
                treatment TEXT, block TEXT, dosage TEXT, weather TEXT,
                temperature REAL, humidity REAL, operator TEXT, remarks TEXT
            )
        """)


# ============================================================
# 小区 CRUD
# ============================================================
def init_plots(field_name=""):
    """初始化 18 个小区"""
    from utils import BLOCKS, TREATMENT_CODES, make_plot_code
    with get_conn() as conn:
        for block in BLOCKS:
            for trt in TREATMENT_CODES:
                code = make_plot_code(block, trt)
                conn.execute(
                    "INSERT OR IGNORE INTO plots (block, treatment, plot_code, field_name) VALUES (?,?,?,?)",
                    (block, trt, code, field_name)
                )


def get_all_plots():
    with get_conn() as conn:
        return pd.read_sql("SELECT * FROM plots ORDER BY block, treatment", conn)


def get_plot_by_code(plot_code):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM plots WHERE plot_code = ?", (plot_code,)).fetchone()
    return dict(row) if row else None


# ============================================================
# 重置所有数据（P0-2：统一入口，走白名单）
# ============================================================
def reset_all_data():
    """清空所有数据表（走白名单校验），并重新初始化小区。"""
    with get_conn() as conn:
        for tbl in _RESET_ORDER:
            _check_table(tbl)
            conn.execute(f"DELETE FROM {tbl}")
    init_plots()
    logger.warning("All data reset — plots re-initialized.")


# ============================================================
# 通用 CRUD（支持复合键）
# ============================================================
def upsert_record(table: str, plot_id: int, data_dict: dict, extra_keys: dict | None = None):
    """插入或更新记录。"""
    _check_table(table)
    if not data_dict:
        return

    with get_conn() as conn:
        cur = conn.cursor()

        where = "plot_id = ?"
        where_vals = [plot_id]
        if extra_keys:
            for k, v in extra_keys.items():
                where += f" AND {k}=?"
                where_vals.append(v)

        existing = cur.execute(f"SELECT id FROM {table} WHERE {where}", where_vals).fetchone()

        if existing:
            sets = ", ".join(f"{k}=?" for k in data_dict.keys())
            vals = list(data_dict.values()) + where_vals
            cur.execute(f"UPDATE {table} SET {sets} WHERE {where}", vals)
        else:
            cols = ["plot_id"]
            if extra_keys:
                cols.extend(extra_keys.keys())
            cols.extend(data_dict.keys())
            placeholders = ", ".join("?" for _ in cols)
            vals = where_vals + list(data_dict.values())
            cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", vals)


def get_record(table: str, plot_id: int, extra_keys: dict | None = None):
    """读取记录"""
    _check_table(table)
    with get_conn() as conn:
        where = "plot_id = ?"
        vals = [plot_id]
        if extra_keys:
            for k, v in extra_keys.items():
                where += f" AND {k}=?"
                vals.append(v)
        row = conn.execute(f"SELECT * FROM {table} WHERE {where}", vals).fetchone()
    return dict(row) if row else None


def get_all_records(table: str, as_dataframe=True):
    """读取某表全部记录（JOIN plots）"""
    _check_table(table)
    with get_conn() as conn:
        if as_dataframe:
            return pd.read_sql(f"""
                SELECT p.plot_code, p.block, p.treatment, t.*
                FROM {table} t
                JOIN plots p ON t.plot_id = p.id
                ORDER BY p.block, p.treatment
            """, conn)
        else:
            rows = conn.execute(f"""
                SELECT p.plot_code, p.block, p.treatment, t.*
                FROM {table} t
                JOIN plots p ON t.plot_id = p.id
                ORDER BY p.block, p.treatment
            """).fetchall()
            return [dict(r) for r in rows]


# ============================================================
# 操作日志 CRUD
# ============================================================
def add_operation(date, op_type, treatment="", block="", time="",
                   dosage="", weather="", temperature=None, humidity=None,
                   operator="", remarks="", plot_id=None):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO operation_log (plot_id, date, time, op_type, treatment, block,
                                       dosage, weather, temperature, humidity, operator, remarks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (plot_id, date, time, op_type, treatment, block,
              dosage, weather, temperature, humidity, operator, remarks))


def get_operations(limit=50):
    with get_conn() as conn:
        return pd.read_sql("""
            SELECT id, date, time, op_type, treatment, block, dosage,
                   weather, temperature, humidity, operator, remarks
            FROM operation_log
            ORDER BY date DESC, time DESC
            LIMIT ?
        """, conn, params=(limit,))


# ============================================================
# 数据完整性统计（一次连接，全部 _check_table）
# ============================================================
def get_completion_stats():
    """返回各表的数据录入完成度。"""
    tables_1to1 = ["phenology", "emergence", "agronomic_traits",
                   "physiological", "yield_data", "quality_data"]
    with get_conn() as conn:
        total_plots = conn.execute("SELECT COUNT(*) FROM plots").fetchone()[0]
        stats = {}

        if total_plots:
            cnt_soil_pre = conn.execute(
                "SELECT COUNT(DISTINCT plot_id) FROM soil_data WHERE phase='播前'"
            ).fetchone()[0]
            cnt_soil_post = conn.execute(
                "SELECT COUNT(DISTINCT plot_id) FROM soil_data WHERE phase='收获后'"
            ).fetchone()[0]
            stats["soil_data"] = {
                "filled": f"{cnt_soil_pre}/{cnt_soil_post}",
                "total": total_plots,
                "pct_pre": round(cnt_soil_pre / total_plots * 100, 1),
                "pct_post": round(cnt_soil_post / total_plots * 100, 1),
                "pct": round((cnt_soil_pre + cnt_soil_post) / (total_plots * 2) * 100, 1),
            }
        else:
            stats["soil_data"] = {"filled": "0/0", "total": 0, "pct": 0, "pct_pre": 0, "pct_post": 0}

        for tbl in tables_1to1:
            _check_table(tbl)
            cnt = conn.execute(
                f"SELECT COUNT(DISTINCT plot_id) FROM {tbl}"
            ).fetchone()[0]
            stats[tbl] = {
                "filled": cnt, "total": total_plots,
                "pct": round(cnt / total_plots * 100, 1) if total_plots else 0,
            }

        stats["operation_log"] = {
            "filled": conn.execute("SELECT COUNT(*) FROM operation_log").fetchone()[0],
            "total": "-", "pct": "-",
        }
    return stats


# ============================================================
# 仪表盘矩阵：用 LEFT JOIN 一次查询 7 张表（降至 7 条 SQL）
# ============================================================
def get_treatment_table_matrix():
    """返回处理 × 数据表完成度矩阵。每个表一条 LEFT JOIN + GROUP BY。"""
    tables_map = {
        "soil_data":  "soil_data",
        "phenology":  "phenology",
        "emergence":  "emergence",
        "agronomic_traits": "agronomic_traits",
        "physiological":   "physiological",
        "yield_data": "yield_data",
        "quality_data": "quality_data",
    }
    from utils import TREATMENT_CODES

    with get_conn() as conn:
        result: dict[str, dict[str, str]] = {trt: {} for trt in TREATMENT_CODES}

        for key, tbl in tables_map.items():
            _check_table(tbl)
            rows = conn.execute(f"""
                SELECT p.treatment, COUNT(DISTINCT t.plot_id) AS cnt
                FROM plots p
                LEFT JOIN {tbl} t ON p.id = t.plot_id
                GROUP BY p.treatment
            """).fetchall()
            cnt_map = {r["treatment"]: r["cnt"] for r in rows}

            # 每个处理有几个小区
            trt_plot_counts = conn.execute("""
                SELECT treatment, COUNT(*) AS total FROM plots GROUP BY treatment
            """).fetchall()
            total_map = {r["treatment"]: r["total"] for r in trt_plot_counts}

            for trt in TREATMENT_CODES:
                cnt = cnt_map.get(trt, 0)
                total = total_map.get(trt, 0)
                result[trt][key] = f"{cnt}/{total}" if total else "0/0"
    return result


# ============================================================
# Excel 导出（支持内存字节流）
# ============================================================
def export_to_excel(filepath_or_buffer):
    """导出所有数据到 Excel（支持路径字符串或 BytesIO）"""
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
# 备份（P0-3：时间戳 + 轮转保留最近 N 个）
# ============================================================
def backup_db():
    """自动备份数据库，保留最近 DB_BACKUP_MAX 个备份"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = DB_PATH + f".{ts}.bak"
    shutil.copy2(DB_PATH, bak_path)

    # 轮转：只保留最近 N 个
    existing = sorted(glob.glob(DB_PATH + ".*.bak"))
    while len(existing) > DB_BACKUP_MAX:
        oldest = existing.pop(0)
        os.remove(oldest)
        logger.info("Removed old backup: %s", oldest)

    logger.info("Backup created: %s", bak_path)
    return bak_path


# ============================================================
# 启动时初始化
# ============================================================
if __name__ == "__main__":
    init_db()
    init_plots()
    print("Database initialized.")
