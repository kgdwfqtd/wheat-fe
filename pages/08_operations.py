# -*- coding: utf-8 -*-
"""操作日志页面"""

import streamlit as st
import pandas as pd
from datetime import date, time as dtime
from wheat_app.repositories.experiment_repository import get_all_plots
from wheat_app.services.operations_service import (
    load_plot_options,
    save_operation_record,
    load_operation_history,
)
from utils import (
    BLOCKS, TREATMENT_CODES, TREATMENT_NAMES, OP_TYPES,
    WEATHER_OPTIONS, NF_SPLIT, get_nf_plot_dose, setup_sidebar, rename_columns_cn
)

st.set_page_config(page_title="操作日志", page_icon="📝", layout="wide")
setup_sidebar()

st.title("📝 操作日志")

plots_df = get_all_plots()
base_options = sorted({row for row in plots_df["base_code"].dropna().tolist() if row})
if not base_options:
    base_options = ["000000000000"]
selected_base = st.selectbox("选择试验基地", options=base_options, key="operation_base")
filtered_plots_df = plots_df[plots_df["base_code"] == selected_base]
plot_options = filtered_plots_df["plot_code"].tolist()

# ============================================================
# 新增操作记录
# ============================================================
st.markdown("### ➕ 新增记录")

with st.form("op_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)

    with col1:
        op_date = st.date_input("日期 *", value=date.today())
        op_time = st.time_input("时间", value=None, step=60)  # 改用 time_input
        op_type = st.selectbox("操作类型 *", options=OP_TYPES)
        st.caption(f"当前基地：{selected_base}")

    with col2:
        op_block = st.selectbox("区组", options=[""] + BLOCKS)
        op_treatment = st.selectbox("处理", options=[""] + TREATMENT_CODES,
                                     format_func=lambda x: f"{x} {TREATMENT_NAMES.get(x,'')}" if x else "—")

    with col3:
        op_weather = st.selectbox("天气", options=[""] + WEATHER_OPTIONS)
        op_temp = st.number_input("气温(℃)", value=None, step=0.5, placeholder="如 25")
        op_humidity = st.number_input("相对湿度(%)", value=None, min_value=0.0, max_value=100.0, step=0.1)

    # 用量提示（纳米铁喷施专用）
    if op_type in ["拌种", "拔节期喷施", "灌浆期喷施"]:
        stage_map = {"拌种": "拌种", "拔节期喷施": "拔节", "灌浆期喷施": "灌浆"}
        stage = stage_map[op_type]
        if op_treatment and op_treatment.startswith("NF-"):
            dose_per_mu = get_nf_plot_dose(op_treatment, stage) / 0.03
            dose_per_plot = get_nf_plot_dose(op_treatment, stage)
            st.info(f"💡 {op_treatment} {stage}期参考：{dose_per_mu:.4f} g/亩（小区：{dose_per_plot:.6f} g）")

    op_dosage = st.text_input("用量/参数", placeholder="如 0.0150g/小区 或 1.2kg/亩")

    col4, col5 = st.columns(2)
    with col4:
        op_operator = st.text_input("操作人", placeholder="姓名")
    with col5:
        op_remarks = st.text_area("备注", placeholder="其他需要记录的信息...", height=68)

    submitted = st.form_submit_button("✅ 提交记录", type="primary", width='stretch')

    if submitted:
        if not op_type:
            st.error("操作类型为必填项！")
        else:
            time_str = op_time.strftime("%H:%M") if op_time else ""
            save_operation_record(
                date=op_date.strftime("%Y-%m-%d"),
                time=time_str,
                op_type=op_type,
                treatment=op_treatment,
                block=op_block,
                dosage=op_dosage,
                weather=op_weather or "",
                temperature=op_temp,
                humidity=op_humidity,
                operator=op_operator or "",
                remarks=op_remarks or "",
                base_code=selected_base,
            )
            st.toast("操作记录已保存！", icon="✅")
            st.rerun()

# ============================================================
# 历史记录查看
# ============================================================
st.markdown("---")
st.markdown("### 📜 历史记录")

col_a, col_b = st.columns([3, 1])
with col_b:
    limit = st.selectbox("显示条数", [10, 20, 50, 100], index=1)
with col_a:
    pass

ops_df = load_operation_history(limit=limit, base_code=selected_base)
if not ops_df.empty:
    st.dataframe(rename_columns_cn(ops_df), width='stretch', hide_index=True)
else:
    st.info("暂无操作记录。")

# ============================================================
# 喷施用量速查表
# ============================================================
st.markdown("---")
st.markdown("### 💊 纳米铁喷施用量速查表")

dose_data = []
for trt in ["NF-0.5", "NF-1.0", "NF-1.5", "NF-2.0"]:
    row = {"处理": f"{trt} {TREATMENT_NAMES.get(trt,'')}"}
    fe_map = {"NF-0.5": 0.5, "NF-1.0": 1.0, "NF-1.5": 1.5, "NF-2.0": 2.0}
    row["亩总用量(g)"] = fe_map[trt]
    for stage, label in [("拌种", "拌种"), ("拔节", "拔节"), ("灌浆", "灌浆")]:
        row[f"{label}\n(亩g)"] = round(fe_map[trt] * NF_SPLIT[stage], 2)
        row[f"{label}\n(小区g)"] = round(fe_map[trt] * NF_SPLIT[stage] * 0.03, 6)
    dose_data.append(row)

dose_df = pd.DataFrame(dose_data)
st.dataframe(dose_df, width='stretch', hide_index=True)
st.caption("* 小区面积以 20 m²（0.03亩）计算")
