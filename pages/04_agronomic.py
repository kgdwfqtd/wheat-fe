# -*- coding: utf-8 -*-
"""农艺性状 — 使用通用表单渲染器"""
from form_helper import render_data_entry_page

FIELD_DEFS = [
    # 分蘖数
    {"key": "tillers_prewinter",    "label": "越冬前分蘖 (个/株)",    "group": "分蘖数（个/株）", "cols": 3},
    {"key": "tillers_postregreen",  "label": "返青后分蘖 (个/株)",    "group": "分蘖数（个/株）", "cols": 3},
    {"key": "tillers_jointing",     "label": "拔节期分蘖 (个/株)",    "group": "分蘖数（个/株）", "cols": 3},
    # 株高
    {"key": "plant_height",         "label": "株高 (cm)，成熟期",     "group": "株高"},
    # 叶面积
    {"key": "lai_jointing",         "label": "拔节期 LAI",            "group": "叶面积指数 (LAI)", "step": 0.01},
    {"key": "lai_heading",          "label": "抽穗期 LAI",            "group": "叶面积指数 (LAI)", "step": 0.01},
    # 地上部干重
    {"key": "dry_weight_jointing",  "label": "拔节期干重 (g/株)",    "group": "地上部干重（g/株）", "cols": 3, "step": 0.01},
    {"key": "dry_weight_heading",   "label": "抽穗期干重 (g/株)",    "group": "地上部干重（g/株）", "cols": 3, "step": 0.01},
    {"key": "dry_weight_maturity",  "label": "成熟期干重 (g/株)",    "group": "地上部干重（g/株）", "cols": 3, "step": 0.01},
    # 根系
    {"key": "root_dry_weight",      "label": "根系干重 (g/株)，拔节期", "group": "根系", "step": 0.01},
]

render_data_entry_page("农艺性状", "🌱", "agronomic_traits", FIELD_DEFS)
