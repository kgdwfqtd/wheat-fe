# -*- coding: utf-8 -*-
"""产量相关业务逻辑"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class YieldCalcResult:
    spikes_per_mu: float
    grains_per_spike: float
    thousand_grain_wt_1: Optional[float]
    thousand_grain_wt_2: Optional[float]
    theoretical_yield: Optional[float]
    actual_yield: Optional[float]
    harvest_index: Optional[float]
    tgw_diff_pct: Optional[float]   # 千粒重两组差异 %
    warnings: list[str]


def calculate_theoretical_yield(spikes_per_mu, grains_per_spike, tgw1=None, tgw2=None):
    """计算理论产量 (kg/亩) = 亩穗数 × 穗粒数 × 平均千粒重 / 1000"""
    if not spikes_per_mu or not grains_per_spike:
        return None

    tgw_vals = [v for v in [tgw1, tgw2] if v is not None]
    if not tgw_vals:
        return None

    avg_tgw = sum(tgw_vals) / len(tgw_vals)
    return round(spikes_per_mu * grains_per_spike * avg_tgw / 1000, 1)


def check_tgw_diff(tgw1, tgw2, warn_threshold=5.0):
    """千粒重两组差异百分比，超过阈值返回警告"""
    if not tgw1 or not tgw2 or (tgw1 + tgw2) == 0:
        return 0.0, []
    diff_pct = abs(tgw1 - tgw2) / ((tgw1 + tgw2) / 2) * 100
    warnings = []
    if diff_pct > warn_threshold:
        warnings.append(f"千粒重两组差异 {diff_pct:.1f}%（>5%），建议复核或重测。")
    return diff_pct, warnings
