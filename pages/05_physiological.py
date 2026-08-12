# -*- coding: utf-8 -*-
"""生理指标 — 使用通用表单渲染器"""
from form_helper import render_data_entry_page

FIELD_DEFS = [
    {"key": "spad_jointing",       "label": "SPAD 拔节期",          "group": "SPAD 值（叶绿素）", "cols": 3},
    {"key": "spad_heading",        "label": "SPAD 抽穗期",          "group": "SPAD 值（叶绿素）", "cols": 3},
    {"key": "spad_filling",        "label": "SPAD 灌浆期",          "group": "SPAD 值（叶绿素）", "cols": 3},
    {"key": "photo_rate_heading",  "label": "抽穗期 (μmol CO₂/m²/s)", "group": "光合速率", "step": 0.01},
    {"key": "photo_rate_filling",  "label": "灌浆期 (μmol CO₂/m²/s)", "group": "光合速率", "step": 0.01},
    {"key": "active_fe_jointing",  "label": "拔节期活性铁",          "group": "叶片活性铁 (mg/kg FW)"},
    {"key": "active_fe_filling",   "label": "灌浆期活性铁",          "group": "叶片活性铁 (mg/kg FW)"},
    {"key": "cat",                 "label": "CAT (U/g/min)",        "group": "抗氧化酶（灌浆期旗叶）"},
    {"key": "pod",                 "label": "POD (U/g/min)",        "group": "抗氧化酶（灌浆期旗叶）"},
]

render_data_entry_page("生理指标", "🔬", "physiological", FIELD_DEFS)
