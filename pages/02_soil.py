# -*- coding: utf-8 -*-
"""土壤基础数据录入 — 使用 upsert_record 复合键"""

import streamlit as st
from database import upsert_record, get_record, get_all_records, get_all_plots

st.set_page_config(page_title="土壤数据", page_icon="🪣")

st.title("🪣 土壤基础数据")

plots_df = get_all_plots()
plot_options = plots_df["plot_code"].tolist()

# ============================================================
# 数据录入
# ============================================================
st.markdown("### 📝 录入 / 编辑")

col1, col2 = st.columns(2)
with col1:
    selected_plot = st.selectbox("选择小区", options=plot_options)
with col2:
    phase = st.selectbox("测定阶段", options=["播前", "收获后"])

plot_info = plots_df[plots_df["plot_code"] == selected_plot]
if not plot_info.empty:
    plot_id = int(plot_info.iloc[0]["id"])
    existing = get_record("soil_data", plot_id, extra_keys={"phase": phase})

    with st.form("soil_form"):
        st.caption(f"当前小区：{selected_plot} | 阶段：{phase}")

        sub1, sub2, sub3 = st.columns(3)
        with sub1:
            ph = st.number_input("pH", value=existing.get("ph") if existing else None,
                                  step=0.1, min_value=0.0, max_value=14.0)
            fe_avail = st.number_input("有效铁 (mg/kg)", value=existing.get("fe_available") if existing else None,
                                        step=0.1, min_value=0.0)
            fe_total = st.number_input("全铁 (g/kg)", value=existing.get("fe_total") if existing else None,
                                        step=0.1, min_value=0.0)

        with sub2:
            om = st.number_input("有机质 (g/kg)", value=existing.get("organic_matter") if existing else None,
                                  step=0.1, min_value=0.0)
            p_avail = st.number_input("有效磷 (mg/kg)", value=existing.get("p_available") if existing else None,
                                       step=0.1, min_value=0.0)
            k_avail = st.number_input("速效钾 (mg/kg)", value=existing.get("k_available") if existing else None,
                                       step=0.1, min_value=0.0)

        with sub3:
            cec = st.number_input("CEC (cmol/kg)", value=existing.get("cec") if existing else None,
                                   step=0.1, min_value=0.0)
            bd = st.number_input("容重 (g/cm³)", value=existing.get("bulk_density") if existing else None,
                                  step=0.01, min_value=0.0)

        submitted = st.form_submit_button("💾 保存", type="primary", width='stretch')

        if submitted:
            data = {}
            fields = {
                "ph": ph, "fe_available": fe_avail, "fe_total": fe_total,
                "organic_matter": om, "p_available": p_avail, "k_available": k_avail,
                "cec": cec, "bulk_density": bd,
            }
            for key, val in fields.items():
                if val is not None:
                    data[key] = val
            if data:
                upsert_record("soil_data", plot_id, data, extra_keys={"phase": phase})
                st.success(f"✅ {selected_plot} {phase} 数据已保存！")
                st.rerun()
            else:
                st.error("请至少填写一项数据。")

# ============================================================
# 数据查看
# ============================================================
st.markdown("---")
st.markdown("### 📊 已录入数据")

soil_df = get_all_records("soil_data")
if not soil_df.empty:
    display_cols = [c for c in soil_df.columns if c not in ['id']]
    st.dataframe(soil_df[display_cols], width='stretch', hide_index=True)
else:
    st.info("尚未录入任何土壤数据。")
