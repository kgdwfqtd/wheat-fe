# -*- coding: utf-8 -*-
"""产量数据 — 带自动计算 + 千粒重差异提示"""

import streamlit as st
from database import upsert_record, get_record, get_all_records, get_all_plots
from form_helper import render_data_entry_page
from utils import setup_sidebar, rename_columns_cn

# 产量页面有自动计算逻辑，不完全使用通用渲染器

st.set_page_config(page_title="产量数据", page_icon="🌾")
setup_sidebar()
st.title("🌾 产量及构成因素")

plots_df = get_all_plots()
plot_options = plots_df["plot_code"].tolist()

st.markdown("### 📝 录入 / 编辑")
selected_plot = st.selectbox("选择小区", options=plot_options)

plot_info = plots_df[plots_df["plot_code"] == selected_plot]
if not plot_info.empty:
    plot_id = int(plot_info.iloc[0]["id"])
    existing = get_record("yield_data", plot_id)

    with st.form("yield_form"):
        st.caption(f"当前小区：{selected_plot}")

        c1, c2, c3 = st.columns(3)
        with c1:
            spikes = st.number_input("亩穗数 (万穗/亩)", value=existing.get("spikes_per_mu") if existing else None,
                                     step=0.1, min_value=0.0)
        with c2:
            grains = st.number_input("穗粒数 (粒/穗)", value=existing.get("grains_per_spike") if existing else None,
                                     step=0.1, min_value=0.0)
        with c3:
            tgw1 = st.number_input("千粒重 第1组 (g)", value=existing.get("thousand_grain_wt_1") if existing else None,
                                   step=0.01, min_value=0.0)

        c4, c5, c6 = st.columns(3)
        with c4:
            tgw2 = st.number_input("千粒重 第2组 (g)", value=existing.get("thousand_grain_wt_2") if existing else None,
                                   step=0.01, min_value=0.0)
        with c5:
            actual = st.number_input("实际产量 (kg/亩)", value=existing.get("actual_yield") if existing else None,
                                     step=0.1, min_value=0.0)
        with c6:
            hi = st.number_input("收获指数", value=existing.get("harvest_index") if existing else None,
                                 step=0.01, min_value=0.0, max_value=1.0)

        # 自动计算理论产量
        if spikes and grains:
            tgw_vals = [v for v in [tgw1, tgw2] if v]
            if tgw_vals:
                tgw_avg = sum(tgw_vals) / len(tgw_vals)
                thy = round(spikes * grains * tgw_avg / 1000, 1)
                st.info(f"📊 理论产量 = {spikes} × {grains} × {tgw_avg} / 1000 = **{thy} kg/亩**")

        # 千粒重差异校验
        if tgw1 and tgw2 and (tgw1 + tgw2) > 0:
            diff_pct = abs(tgw1 - tgw2) / ((tgw1 + tgw2) / 2) * 100
            if diff_pct > 5:
                st.warning(f"⚠️ 千粒重两组差 {diff_pct:.1f}%（>5%），建议复核或重测。")

        submitted = st.form_submit_button("💾 保存产量数据", type="primary", width='stretch')

        if submitted:
            data = {}
            fields = {
                "spikes_per_mu": spikes, "grains_per_spike": grains,
                "thousand_grain_wt_1": tgw1, "thousand_grain_wt_2": tgw2,
                "actual_yield": actual, "harvest_index": hi,
            }
            for key, val in fields.items():
                if val is not None and val >= 0:
                    data[key] = val
            # 计算理论产量
            if spikes and grains:
                tgv = [v for v in [tgw1, tgw2] if v]
                if tgv:
                    data["theoretical_yield"] = round(spikes * grains * (sum(tgv) / len(tgv)) / 1000, 1)
            if data:
                upsert_record("yield_data", plot_id, data)
                st.success(f"✅ {selected_plot} 产量数据已保存！")
                st.rerun()
            else:
                st.error("请至少填写一项数据。")

# ============================================================
# 已录入数据 + 统计
# ============================================================
st.markdown("---")
st.markdown("### 📊 已录入数据")
yield_df = get_all_records("yield_data")
if not yield_df.empty:
    display_cols = [c for c in yield_df.columns if c not in ['id', 'plot_id']]
    st.dataframe(rename_columns_cn(yield_df[display_cols]), width='stretch', hide_index=True)

    st.markdown("**产量快速统计**")
    sc = st.columns(4)
    with sc[0]:
        if 'actual_yield' in yield_df.columns and yield_df['actual_yield'].notna().any():
            st.metric("平均亩产", f"{yield_df['actual_yield'].mean():.1f} kg")
        else:
            st.metric("平均亩产", "N/A")
    with sc[1]:
        if 'actual_yield' in yield_df.columns and yield_df['actual_yield'].notna().any():
            st.metric("最高亩产", f"{yield_df['actual_yield'].max():.1f} kg")
        else:
            st.metric("最高亩产", "N/A")
    with sc[2]:
        if 'thousand_grain_wt_1' in yield_df.columns and yield_df['thousand_grain_wt_1'].notna().any():
            avg_tgw = ((yield_df['thousand_grain_wt_1'] + yield_df['thousand_grain_wt_2']) / 2).mean()
            st.metric("平均千粒重", f"{avg_tgw:.1f} g")
        else:
            st.metric("平均千粒重", "N/A")
    with sc[3]:
        cnt = yield_df['actual_yield'].notna().sum() if 'actual_yield' in yield_df.columns else 0
        st.metric("已录入", f"{int(cnt)}/18")
else:
    st.info("暂无产量数据。")
