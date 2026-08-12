# -*- coding: utf-8 -*-
"""出苗率相关业务逻辑"""

from typing import Optional


def calc_emergence_rate(emerged: Optional[int], seeds_sown: Optional[int]) -> Optional[float]:
    """计算出苗率 (%)。若 seeds_sown 为 0 或 None，返回 None。"""
    if not seeds_sown or seeds_sown <= 0:
        return None
    if emerged is None:
        return None
    return round(emerged / seeds_sown * 100, 1)


def validate_emergence(emerged: Optional[int], seeds_sown: Optional[int]) -> list[str]:
    """出苗数逻辑校验：出苗数 > 播种数时返回警告"""
    warnings = []
    if emerged is not None and seeds_sown is not None and seeds_sown > 0:
        if emerged > seeds_sown:
            warnings.append(f"出苗数 ({emerged}) 大于播种粒数 ({seeds_sown})，请检查！")
    return warnings
