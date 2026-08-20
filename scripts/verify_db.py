#!/usr/bin/env python3
"""验证 PostgreSQL 中的数据写入情况。

用法：
    # PowerShell
    $env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/wheat_fe"
    python scripts/verify_db.py

"""
from __future__ import annotations
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so top-level imports (e.g. `database`) work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import get_all_bases, get_all_plots, get_base_by_code


def main():
    print("查询所有基地...")
    bases = get_all_bases()
    try:
        print(bases.head())
    except Exception:
        print(bases)

    if bases is None or bases.empty:
        print("没有找到任何基地。请先运行 scripts/seed_data.py 填充示例数据。")
        return

    # 检查每个基地是否有小区
    for idx, row in bases.iterrows():
        base_code = row.get("base_code")
        print(f"基地 {base_code} -> 详情: ")
        details = get_base_by_code(base_code)
        print(details)
        plots = get_all_plots(base_code=base_code)
        print(f"小区数: {len(plots) if plots is not None else 0}")

    print("验证完成。")


if __name__ == "__main__":
    main()
