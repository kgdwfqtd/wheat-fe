# -*- coding: utf-8 -*-
"""小区相关业务逻辑。"""

import io
import zipfile

import pandas as pd

from utils import TREATMENT_NAMES, TREATMENT_COLORS
from wheat_app.repositories.experiment_repository import get_all_plots, reset_all_data


def load_plots_data():
    """返回小区数据表。"""
    return get_all_plots()


def build_plot_display_rows(plots_df):
    """构建小区列表展示数据。"""
    display_data = []
    for _, row in plots_df.iterrows():
        trt = row["treatment"]
        display_data.append({
            "小区编号": row["plot_code"],
            "区组": row["block"],
            "处理代号": trt,
            "处理名称": TREATMENT_NAMES.get(trt, ""),
            "面积(m²)": row["area_m2"],
            "田块": row.get("field_name", "") or "",
        })
    return pd.DataFrame(display_data)


def build_qr_zip_for_block(plots_df, block, base_url, api_base_url):
    """打包某区组二维码。"""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, row in plots_df[plots_df["block"] == block].iterrows():
            plot_code = row["plot_code"]
            from utils import generate_qr_code
            png_bytes, _, _ = generate_qr_code(plot_code, base_url, api_base=api_base_url, box_size=8, border=3)
            zf.writestr(f"QR_{plot_code}.png", png_bytes)
    zip_buf.seek(0)
    return zip_buf.read()


def build_qr_zip_for_all(plots_df, base_url, api_base_url):
    """打包全部二维码。"""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, row in plots_df.iterrows():
            plot_code = row["plot_code"]
            from utils import generate_qr_code
            png_bytes, _, _ = generate_qr_code(plot_code, base_url, api_base=api_base_url, box_size=8, border=3)
            zf.writestr(f"QR_{plot_code}.png", png_bytes)
    zip_buf.seek(0)
    return zip_buf.read()


def reset_experiment_data():
    """重置实验数据。"""
    reset_all_data()


def get_layout_summary(plots_df, block, treatment_codes, treatment_colors):
    """返回区组布局汇总信息。"""
    block_df = plots_df[plots_df["block"] == block]
    layout_rows = []
    for _, row in block_df.iterrows():
        trt = row["treatment"]
        layout_rows.append({
            "plot_code": row["plot_code"],
            "treatment": trt,
            "name": TREATMENT_NAMES.get(trt, ""),
            "color": treatment_colors.get(trt, "#FFF"),
        })
    return layout_rows


__all__ = [
    "load_plots_data",
    "build_plot_display_rows",
    "build_qr_zip_for_block",
    "build_qr_zip_for_all",
    "reset_experiment_data",
    "get_layout_summary",
]
