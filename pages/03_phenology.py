# -*- coding: utf-8 -*-
"""物候期 & 出苗率 — 特殊页面（双 Tab + 自动计算），不使用通用渲染器"""

import streamlit as st
from datetime import date
from wheat_app.repositories.experiment_repository import get_all_plots, get_record, get_all_records, upsert_record
from wheat_app.services.phenology_service import (
    load_plot_options,
    load_phenology_record,
    save_phenology_record,
    load_emergence_record,
    save_emergence_record,
    load_phenology_table,
    load_emergence_table,
)
from utils import setup_sidebar, rename_columns_cn

st.set_page_config(page_title="物候期 & 出苗", page_icon="📅", layout="wide")
setup_sidebar()
st.title("📅 物候期 & 出苗调查")

plots_df = get_all_plots()
base_options = sorted({row for row in plots_df["base_code"].dropna().tolist() if row})
if not base_options:
    base_options = ["000000000000"]
# Extract query parameters to pre-select base and plot via QR code redirect
query_params = st.experimental_get_query_params()
plot_param = query_params.get("plot", [None])[0]
default_base = None
if plot_param:
    matching_row = plots_df[plots_df["plot_code"] == plot_param]
    if not matching_row.empty:
        default_base = matching_row.iloc[0]["base_code"]

selected_base = st.selectbox(
    "选择试验基地",
    options=base_options,
    key="base_selector",
    index=base_options.index(default_base) if default_base and default_base in base_options else 0,
)
filtered_plots_df = plots_df[plots_df["base_code"] == selected_base]
plot_options = filtered_plots_df["plot_code"].tolist()

tab1, tab2 = st.tabs(["🌿 物候期", "🌱 出苗调查"])

# ============================================================
# Tab 1: 物候期
# ============================================================
with tab1:
    selected_plot = st.selectbox("选择小区", options=plot_options, key="pheno_plot")
    plot_info = filtered_plots_df[filtered_plots_df["plot_code"] == selected_plot]
    if not plot_info.empty:
        plot_id = int(plot_info.iloc[0]["id"])
        existing = load_phenology_record(plot_id)

        with st.form("pheno_form"):
            st.caption(f"当前基地：{selected_base} | 当前小区：{selected_plot}")

            stages = [
                ("sowing", "播种"), ("emergence", "出苗"), ("tillering", "分蘖"),
                ("overwinter", "越冬"), ("regreening", "返青"), ("jointing", "拔节"),
                ("heading", "抽穗"), ("flowering", "开花"), ("filling", "灌浆"),
                ("maturity", "成熟"),
            ]
            inputs = {}
            cols = st.columns(3)
            for i, (key, label) in enumerate(stages):
                ex_date = None
                if existing and existing.get(key):
                    try:
                        parts = existing[key].split("-")
                        ex_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
                    except Exception:
                        pass
                with cols[i % 3]:
                    inputs[key] = st.date_input(f"{label}期", value=ex_date, key=f"ph_{key}")

            submitted = st.form_submit_button("💾 保存物候期", type="primary", width='stretch')
            if submitted:
                data = {}
                for key, _ in stages:
                    d = inputs[key]
                    if d:
                        data[key] = d.strftime("%Y-%m-%d")
                if data:
                    save_phenology_record(plot_id, data, base_code=selected_base)
                    st.toast(f"✅ {selected_plot} 物候期已保存！", icon="✅")
                    st.rerun()
                else:
                    st.error("请至少填写一个日期。")

# ============================================================
# Tab 2: 出苗率
# ============================================================
with tab2:
    selected_plot2 = st.selectbox("选择小区", options=plot_options, key="emerg_plot")
    plot_info2 = filtered_plots_df[filtered_plots_df["plot_code"] == selected_plot2]
    if not plot_info2.empty:
        plot_id2 = int(plot_info2.iloc[0]["id"])
        existing2 = load_emergence_record(plot_id2)

        with st.form("emerg_form"):
            st.caption(f"当前基地：{selected_base} | 当前小区：{selected_plot2}")

            c1, c2 = st.columns(2)
            with c1:
                seeds = st.number_input("播种粒数", value=existing2.get("seeds_sown") if existing2 else None,
                                         min_value=0, step=1)
                em7 = st.number_input("出苗数 (7天)", value=existing2.get("emerged_7d") if existing2 else None,
                                       min_value=0, step=1)
            with c2:
                em14 = st.number_input("出苗数 (14天)", value=existing2.get("emerged_14d") if existing2 else None,
                                        min_value=0, step=1)
                bs = st.number_input("基本苗 (万/亩)", value=existing2.get("basic_seedlings") if existing2 else None,
                                      step=0.1, min_value=0.0)

            # 自动算出苗率 + 校验
            if seeds and seeds > 0:
                rate7 = round(em7 / seeds * 100, 1) if em7 else None
                rate14 = round(em14 / seeds * 100, 1) if em14 else None
                if rate7 is not None or rate14 is not None:
                    st.caption(f"📊 自动计算：出苗率7d = {rate7}% | 出苗率14d = {rate14}%")
                # 业务校验
                if em7 is not None and em7 > seeds:
                    st.warning("⚠️ 出苗数(7d) 大于播种粒数，请检查！")
                if em14 is not None and em14 > seeds:
                    st.warning("⚠️ 出苗数(14d) 大于播种粒数，请检查！")

            submitted2 = st.form_submit_button("💾 保存出苗数据", type="primary", width='stretch')
            if submitted2:
                data = {}
                if seeds is not None and seeds >= 0:
                    data["seeds_sown"] = int(seeds)
                if em7 is not None and em7 >= 0:
                    data["emerged_7d"] = int(em7)
                    data["rate_7d"] = round(em7 / seeds * 100, 1) if seeds else None
                if em14 is not None and em14 >= 0:
                    data["emerged_14d"] = int(em14)
                    data["rate_14d"] = round(em14 / seeds * 100, 1) if seeds else None
                if bs is not None and bs >= 0:
                    data["basic_seedlings"] = bs
                data = {k: v for k, v in data.items() if v is not None}
                if data:
                    save_emergence_record(plot_id2, data, base_code=selected_base)
                    st.toast(f"✅ {selected_plot2} 出苗数据已保存！", icon="✅")
                    st.rerun()
                else:
                    st.error("请至少填写一项数据。")

# ============================================================
# 已录入数据汇总
# ============================================================
st.markdown("---")
pheno_df = load_phenology_table()
emerg_df = load_emergence_table()

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("**物候期记录**")
    if not pheno_df.empty:
        disp = [c for c in pheno_df.columns if c not in ['id', 'plot_id']]
        st.dataframe(rename_columns_cn(pheno_df[disp]), width='stretch', hide_index=True)
    else:
        st.info("暂无数据")
with col_b:
    st.markdown("**出苗调查**")
    if not emerg_df.empty:
        disp = [c for c in emerg_df.columns if c not in ['id', 'plot_id']]
        st.dataframe(rename_columns_cn(emerg_df[disp]), width='stretch', hide_index=True)
    else:
        st.info("暂无数据")
