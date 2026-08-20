#!/usr/bin/env python3
"""将示例数据写入 PostgreSQL，用于开发/测试。

用法示例：
    # PowerShell
    $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/wheat_fe"
    python scripts/seed_data.py

脚本依赖：psycopg2、pandas
"""
from __future__ import annotations
import os
from datetime import datetime
import sys
from pathlib import Path

# Ensure project root is on sys.path so top-level imports (e.g. `database`) work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 使用项目的 database.py 中的函数
from database import init_db, create_experiment_base, update_experiment_base
from database import get_all_bases, get_all_plots


SAMPLE_BASES = [
    {"base_code": "510105010202608", "base_name": "示例基地A", "admin_code": "510105", "address": "四川省成都市"},
    {"base_code": "510105010302608", "base_name": "示例基地B", "admin_code": "510105", "address": "四川省成都市"},
]

PLOTS_PER_BASE = [
    {"block": "Ⅰ", "treatment": "CK", "plot_code": None},
    {"block": "Ⅰ", "treatment": "FS", "plot_code": None},
    {"block": "Ⅱ", "treatment": "NF-1.0", "plot_code": None},
    {"block": "Ⅱ", "treatment": "NF-1.5", "plot_code": None},
]


def seed():
    print("初始化数据库表（如果尚未创建）...")
    init_db()

    print("创建示例基地与小区...")
    for base in SAMPLE_BASES:
        try:
            create_experiment_base(
                base_code=base["base_code"],
                base_name=base["base_name"],
                admin_code=base.get("admin_code"),
                address=base.get("address"),
            )
            print(f"已创建基地 {base['base_code']}")
            # 为示例基地填入经纬度，便于天气查询（示例使用成都市中心坐标）
            try:
                update_experiment_base(base["base_code"], latitude=30.5728, longitude=104.0668, base_name=base["base_name"])
            except Exception:
                pass
        except Exception as e:
            print(f"创建基地失败（可能已存在）：{e}")

    # 通过直接 SQL 插入小区（如果框架没有暴露创建小区的函数）
    # 这里简单调用 database.init_plots() 如果存在
    try:
        from database import init_plots
        init_plots()
        print("已初始化小区（init_plots()）")
    except Exception:
        print("init_plots() 不可用，跳过自动小区初始化。请手动添加小区或更新脚本。")

    print("示例数据填充完成。可用 get_all_bases() / get_all_plots() 验证。")


if __name__ == "__main__":
    seed()
