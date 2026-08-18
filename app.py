# -*- coding: utf-8 -*-
"""纳米铁肥小麦试验记录程序 — 主入口 & 仪表盘"""

import sys
import streamlit as st
import pandas as pd
from wheat_app.services.experiment_service import get_dashboard_snapshot
from utils import TREATMENT_COLORS, TREATMENT_NAMES, TREATMENT_CODES, setup_sidebar, rename_columns_cn
from wheat_app.repositories.experiment_repository import init_db, init_plots

if __name__ == "__main__":
    from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx

    if get_script_run_ctx() is None:
        print("请使用 `streamlit run app.py` 启动本应用。")
        sys.exit(1)

st.set_page_config(
    page_title="纳米铁肥小麦试验记录",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 初始化数据库（缓存一次，重置时手动清除）
# ============================================================
@st.cache_resource
def setup_database():
    init_db()
    init_plots()


def clear_db_cache():
    """重置后清除缓存"""
    st.cache_resource.clear()


setup_database()

setup_sidebar()

# ============================================================
# 主区域
# ============================================================
st.title("🌾 纳米铁肥小麦试验记录系统")
st.caption("基于《纳米铁肥在小麦上的应用效果对比试验方案》编制")

# ----- 数据概览卡片 -----
dashboard = get_dashboard_snapshot()
stats = dashboard["stats"]
plots_df = dashboard["plots_df"]
total_plots = dashboard.get("total_plots", len(plots_df) if plots_df is not None else 0)
base_count = dashboard.get("base_count", 0)

st.markdown("### 📊 数据录入概览")

cols = st.columns(5)
with cols[0]:
    st.metric("小区总数", total_plots)
with cols[1]:
    st.metric("基地总数", base_count)
with cols[2]:
    completed = sum(
        1 for k, v in stats.items()
        if k != "operation_log" and isinstance(v, dict) and v.get("pct", 0) == 100
    )
    st.metric("完成 100% 的表", f"{completed}/7")
with cols[3]:
    op_count = stats.get("operation_log", {}).get("filled", 0)
    st.metric("操作日志条数", op_count)
with cols[4]:
    pcts = []
    for k, v in stats.items():
        if k != "operation_log" and isinstance(v, dict):
            p = v.get("pct", 0)
            if isinstance(p, (int, float)):
                pcts.append(p)
    avg_pct = round(sum(pcts) / len(pcts), 1) if pcts else 0
    st.metric("平均完成度", f"{avg_pct}%")

# ----- 进度条 -----
st.markdown("#### 各数据表完成度")
progress_cols = st.columns(4)
tbl_display = [
    ("soil_data", "🪣 土壤数据"),
    ("phenology", "📅 物候期"),
    ("emergence", "🌱 出苗调查"),
    ("agronomic_traits", "🌿 农艺性状"),
    ("physiological", "🔬 生理指标"),
    ("yield_data", "🌾 产量数据"),
    ("quality_data", "🏆 品质数据"),
]
for i, (key, label) in enumerate(tbl_display):
    with progress_cols[i % 4]:
        pct_val = stats.get(key, {}).get("pct", 0)
        pct_val = pct_val if isinstance(pct_val, (int, float)) else 0
        st.metric(label, f"{pct_val}%")
        st.progress(pct_val / 100)

# ----- 土壤数据详情 -----
soil_stats = stats.get("soil_data", {})
if isinstance(soil_stats.get("pct_pre"), (int, float)):
    with st.expander("🪣 土壤数据详情（播前 / 收获后）"):
        c1, c2 = st.columns(2)
        with c1:
            st.metric("播前完成", f"{soil_stats.get('pct_pre', 0)}%")
        with c2:
            st.metric("收获后完成", f"{soil_stats.get('pct_post', 0)}%")

# ----- 处理 × 数据表完成度矩阵（一次查询，无 N+1）-----
st.markdown("---")
st.markdown("### 📋 各处理 × 数据表 完成情况")

tables_1to1 = ["phenology", "emergence", "agronomic_traits",
               "physiological", "yield_data", "quality_data"]
tbl_short = ["土壤", "物候", "出苗", "农艺", "生理", "产量", "品质"]
all_tbl_keys = ["soil_data"] + tables_1to1

matrix = dashboard["treatment_matrix"]
matrix_data = []
for trt in TREATMENT_CODES:
    row_data = [trt, TREATMENT_NAMES.get(trt, "")]
    trt_matrix = matrix.get(trt, {})
    for tbl in all_tbl_keys:
        row_data.append(trt_matrix.get(tbl, "—"))
    matrix_data.append(row_data)

matrix_df = pd.DataFrame(matrix_data, columns=["处理", "名称"] + tbl_short)
st.dataframe(matrix_df, width='stretch', hide_index=True)

# ----- 最近操作日志 -----
st.markdown("---")
st.markdown("### 📝 最近操作记录")

ops_df = dashboard["recent_ops"]
if not ops_df.empty:
    st.dataframe(rename_columns_cn(ops_df), width='stretch', hide_index=True)
else:
    st.info("暂无操作记录。请在「操作日志」页面记录试验操作。")

# ----- 底部信息 -----
st.markdown("---")
st.caption("💡 提示：使用左侧导航栏切换页面，在手机上也可方便使用。数据存储在本地 experiment.db 文件中。")
