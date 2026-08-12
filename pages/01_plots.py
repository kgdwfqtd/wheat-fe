# -*- coding: utf-8 -*-
"""小区管理页面"""

import streamlit as st
import pandas as pd
from database import init_plots, get_all_plots, reset_all_data
from utils import BLOCKS, TREATMENT_CODES, TREATMENT_NAMES, TREATMENT_COLORS, setup_sidebar

st.set_page_config(page_title="小区管理", page_icon="📋")
setup_sidebar()

st.title("📋 小区管理")

plots_df = get_all_plots()

if plots_df.empty:
    st.warning("尚未初始化小区数据，请点击下方按钮初始化。")
    if st.button("🔧 一键初始化 18 个小区", type="primary", width='stretch'):
        init_plots()
        st.rerun()
else:
    st.markdown("### 小区列表")
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
    st.dataframe(pd.DataFrame(display_data), width='stretch', hide_index=True)

    st.markdown("---")
    st.markdown("### 🗺️ 田间布局示意")
    for block in BLOCKS:
        cols = st.columns(len(TREATMENT_CODES) + 1)
        cols[0].markdown(f"**区组 {block}**")
        block_df = plots_df[plots_df["block"] == block]
        for i, (_, row) in enumerate(block_df.iterrows()):
            trt = row["treatment"]
            color = TREATMENT_COLORS.get(trt, "#FFF")
            code = row["plot_code"]
            cols[i + 1].markdown(
                f'<div style="background:{color};padding:8px;border-radius:4px;'
                f'text-align:center;font-size:13px;border:1px solid #999;">'
                f'<b>{code}</b><br><small>{TREATMENT_NAMES.get(trt,"")}</small></div>',
                unsafe_allow_html=True
            )

    # ---- 重置（P0-2：走 reset_all_data 统一入口）----
    st.markdown("---")
    st.markdown("### ⚠️ 高级操作")
    with st.expander("重置小区数据"):
        st.warning("⚠️ 重置将 **永久删除** 所有小区及相关数据，此操作不可恢复！")
        st.markdown("请在下方输入 **确认重置** 四个字以继续：")
        confirm_text = st.text_input("输入确认文字", placeholder="确认重置", key="reset_confirm")

        if st.button("🗑️ 确认重置所有数据", type="secondary",
                     disabled=(confirm_text != "确认重置")):
            reset_all_data()
            st.cache_resource.clear()
            st.success("✅ 已清空所有数据并重新初始化小区。")
            st.rerun()
