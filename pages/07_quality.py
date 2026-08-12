# -*- coding: utf-8 -*-
"""品质指标 — 使用通用表单渲染器"""
from form_helper import render_data_entry_page

FIELD_DEFS = [
    {"key": "grain_protein",     "label": "籽粒蛋白质 (%)",      "step": 0.01, "max": 30.0, "cols": 3},
    {"key": "wet_gluten",        "label": "湿面筋 (%)",          "step": 0.01, "max": 60.0, "cols": 3},
    {"key": "sds_sedimentation", "label": "SDS沉降值 (mL)",      "step": 0.1,              "cols": 3},
    {"key": "grain_fe",          "label": "籽粒铁含量 (mg/kg)",  "step": 0.01, "group": "铁含量"},
    {"key": "flour_fe",          "label": "面粉铁含量 (mg/kg)",  "step": 0.01, "group": "铁含量"},
]

render_data_entry_page("品质数据", "🏆", "quality_data", FIELD_DEFS)
