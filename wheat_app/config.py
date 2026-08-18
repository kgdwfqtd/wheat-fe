# -*- coding: utf-8 -*-
"""统一配置中心：从环境变量加载配置，避免在代码中硬编码敏感参数。"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def _decode_bytes(value: bytes) -> str:
    """把可能带有 Windows 代码页的 bytes 转为安全字符串。"""
    for encoding in ("utf-8-sig", "utf-8", "gbk", "cp936", "gb18030", "latin-1"):
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            continue
    return value.decode("utf-8", errors="replace")


def _normalize_env_value(value, default: str = "") -> str:
    """确保环境变量读取到的是可用的字符串；避免无效的 bytes 进入连接参数。"""
    if value is None:
        return default
    if isinstance(value, bytes):
        return _decode_bytes(value).strip()
    text = str(value).strip()
    return text if text else default


def _read_env_file_text(path: Path) -> str:
    """读取 .env 文件，兼容 UTF-8/GBK/CP936 等常见 Windows 编码。"""
    raw = path.read_bytes()
    return _decode_bytes(raw)


def _load_env_file() -> None:
    """加载项目根目录的 .env 文件（如果存在）。"""
    if not ENV_FILE.exists():
        return

    for line in _read_env_file_text(ENV_FILE).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _normalize_env_value(value.strip().strip("\"'"), "")
        if key and value:
            os.environ.setdefault(key, value)


_load_env_file()

# ---- PostgreSQL 数据库配置 ----
POSTGRES_HOST = _normalize_env_value(os.getenv("POSTGRES_HOST"), "localhost")
POSTGRES_PORT = int(_normalize_env_value(os.getenv("POSTGRES_PORT"), "5432"))
POSTGRES_USER = _normalize_env_value(os.getenv("POSTGRES_USER"), "postgres")
POSTGRES_PASSWORD = _normalize_env_value(os.getenv("POSTGRES_PASSWORD"), "postgres")
POSTGRES_DB = _normalize_env_value(os.getenv("POSTGRES_DB"), "wheat_fe")

# 统一的数据库连接字典（兼容 psycopg2）
DB_CONFIG = {
    "host": POSTGRES_HOST,
    "port": POSTGRES_PORT,
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
    "dbname": POSTGRES_DB,
}

# SQLAlchemy 风格 URL（兼容旧代码）
DB_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:"
    f"{POSTGRES_PORT}/{POSTGRES_DB}"
)
DB_BACKUP_MAX = int(os.getenv("DB_BACKUP_MAX", "5"))

# ---- 小区与业务参数 ----
PLOT_AREA_M2 = float(os.getenv("PLOT_AREA_M2", "20.0"))
PLOT_RATIO = PLOT_AREA_M2 / 666.67

NF_SPLIT = {"拌种": 0.50, "拔节": 0.30, "灌浆": 0.20}
NF_SPRAY_WATER_L_PER_MU = float(os.getenv("NF_SPRAY_WATER_L_PER_MU", "30"))

TKW_DIFF_WARN_PCT = float(os.getenv("TKW_DIFF_WARN_PCT", "5.0"))
EMERGENCE_RATE_WARN = os.getenv("EMERGENCE_RATE_WARN", "true").lower() == "true"

# ---- Streamlit 页面配置 ----
PAGE_TITLE = os.getenv("PAGE_TITLE", "纳米铁肥小麦试验记录")
PAGE_ICON = os.getenv("PAGE_ICON", "🌾")

# ---- 兼容旧命名 ----
POSTGRES = DB_CONFIG
PROJECT_ROOT = BASE_DIR
