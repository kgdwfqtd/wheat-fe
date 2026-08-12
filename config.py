# -*- coding: utf-8 -*-
"""集中配置 — 所有可调参数一处管理"""

import os

# ---- 数据库 ----
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DATA_DIR, "experiment.db")
DB_BACKUP_MAX = 5  # 保留最近 N 个备份

# ---- 小区 ----
PLOT_AREA_M2 = 20.0         # 小区面积 (m²)
PLOT_RATIO = PLOT_AREA_M2 / 666.67  # 折算亩系数

# ---- 纳米铁 ----
NF_SPLIT = {"拌种": 0.50, "拔节": 0.30, "灌浆": 0.20}
NF_SPRAY_WATER_L_PER_MU = 30  # 每亩喷液量 (L)

# ---- 业务校验 ----
TKW_DIFF_WARN_PCT = 5.0       # 千粒重两组差异警告阈值 (%)
EMERGENCE_RATE_WARN = True     # 出苗数 > 播种数时警告

# ---- Streamlit ----
PAGE_TITLE = "纳米铁肥小麦试验记录"
PAGE_ICON = "🌾"
