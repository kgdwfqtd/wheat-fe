# -*- coding: utf-8 -*-
"""常量定义 & 工具函数"""

# ============================================================
# 处理定义 — fe_total 统一为 float，单位另存
# ============================================================
TREATMENTS = [
    {"code": "CK",     "name": "空白对照",       "color": "#E8E8E8", "fe_total": 0.0,   "fe_unit": "g/亩"},
    {"code": "FS",     "name": "硫酸亚铁对照",   "color": "#DAE8FC", "fe_total": 2000.0, "fe_unit": "g/亩"},  # 2.0 kg/亩 = 2000 g/亩
    {"code": "NF-0.5", "name": "纳米铁 半量",    "color": "#E1F5D5", "fe_total": 0.5,    "fe_unit": "g/亩"},
    {"code": "NF-1.0", "name": "纳米铁 标准量",  "color": "#D5E8D4", "fe_total": 1.0,    "fe_unit": "g/亩"},
    {"code": "NF-1.5", "name": "纳米铁 1.5倍量", "color": "#C8E6C9", "fe_total": 1.5,    "fe_unit": "g/亩"},
    {"code": "NF-2.0", "name": "纳米铁 2倍量",   "color": "#A5D6A7", "fe_total": 2.0,    "fe_unit": "g/亩"},
]

TREATMENT_CODES = [t["code"] for t in TREATMENTS]
TREATMENT_COLORS = {t["code"]: t["color"] for t in TREATMENTS}
TREATMENT_NAMES = {t["code"]: t["name"] for t in TREATMENTS}
TREATMENT_FE_TOTAL = {t["code"]: t["fe_total"] for t in TREATMENTS}
TREATMENT_FE_UNIT = {t["code"]: t["fe_unit"] for t in TREATMENTS}

BLOCKS = ["Ⅰ", "Ⅱ", "Ⅲ"]

# ============================================================
# 纳米铁各时期分配比例
# ============================================================
NF_SPLIT = {
    "拌种": 0.50,
    "拔节": 0.30,
    "灌浆": 0.20,
}

# 纳米铁亩用量 → 每小区用量系数（20 m² = 0.03 亩）
PLOT_RATIO = 0.03


def get_nf_plot_dose(treatment_code, stage=None):
    """获取某处理某时期的纳米铁小区用量(g)。
    仅对 NF- 系列处理有效；FS/CK 返回 0。
    """
    total = TREATMENT_FE_TOTAL.get(treatment_code, 0)
    if not isinstance(total, (int, float)) or total <= 0 or not treatment_code.startswith("NF-"):
        return 0.0
    if stage and stage in NF_SPLIT:
        return round(total * NF_SPLIT[stage] * PLOT_RATIO, 6)
    return round(total * PLOT_RATIO, 6)


# ============================================================
# 操作类型
# ============================================================
OP_TYPES = [
    "拌种", "拔节期喷施", "灌浆期喷施",
    "播种", "灌溉", "施肥（基肥）",
    "除草", "病虫害防治", "取样", "调查/测定", "其他",
]

# ============================================================
# 天气选项
# ============================================================
WEATHER_OPTIONS = ["晴", "多云", "阴", "小雨", "中雨", "大雨", "雾", "雪", "大风"]


# ============================================================
# 工具函数
# ============================================================
def make_plot_code(block, treatment):
    """生成小区编号，如 Ⅰ-CK"""
    return f"{block}-{treatment}"
