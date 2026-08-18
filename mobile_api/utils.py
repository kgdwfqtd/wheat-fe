# -*- coding: utf-8 -*-
"""工具函数与常量（移动端独立版本）"""

BLOCKS = ["Ⅰ", "Ⅱ", "Ⅲ"]

TREATMENT_CODES = ["CK", "FS", "NF-0.5", "NF-1.0", "NF-1.5", "NF-2.0"]

TREATMENT_NAMES = {
    "CK": "空白对照",
    "FS": "硫酸亚铁对照",
    "NF-0.5": "纳米铁 半量",
    "NF-1.0": "纳米铁 标准量",
    "NF-1.5": "纳米铁 1.5倍量",
    "NF-2.0": "纳米铁 2倍量",
}

# 操作类型
OP_TYPES = [
    "拌种", "拔节期喷施", "灌浆期喷施",
    "播种", "灌溉", "施肥（基肥）",
    "除草", "病虫害防治", "取样", "调查/测定", "其他",
]


def make_plot_code(block, treatment):
    """生成小区编号"""
    return f"{block}-{treatment}"