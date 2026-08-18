# -*- coding: utf-8 -*-
"""试验基地管理页面"""

import streamlit as st

from wheat_app.repositories.experiment_repository import (
    create_experiment_base,
    get_all_bases,
    get_all_plots,
    delete_experiment_base,
)
from utils import setup_sidebar

st.set_page_config(page_title="试验基地管理", page_icon="🏢", layout="wide")
setup_sidebar()
st.title("🏢 试验基地管理")

st.caption("基地编号规则：6位县级行政区划代码 + 2位基地编号 + 年 + 月，例如 510105010202608")

bases_df = get_all_bases()
plots_df = get_all_plots()

# 初始化编辑器状态
if "edit_base_code" not in st.session_state:
    st.session_state.edit_base_code = None

with st.form("base_create_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        base_code = st.text_input("基地编号 *", placeholder="如 510105010202608")
    with col2:
        base_name = st.text_input("基地名称 *", placeholder="如 试验基地A")
    with col3:
        admin_code = st.text_input("县级行政区代码", placeholder="如 510105")
    remarks = st.text_area("备注", height=80)
    submitted = st.form_submit_button("➕ 新增基地", type="primary", use_container_width=True)

    if submitted:
        base_code = base_code.strip()
        if not base_code or not base_name.strip():
            st.error("基地编号和名称不能为空。")
        else:
            try:
                create_experiment_base(
                    base_code=base_code,
                    base_name=base_name.strip(),
                    admin_code=admin_code.strip() or base_code[:6],
                    remarks=remarks.strip(),
                )
                st.success(f"✅ 基地 {base_code} 已创建。")
                st.rerun()
            except Exception as exc:
                st.error(f"创建失败：{exc}")

st.markdown("---")
st.markdown("### ✏️ 修改基地信息")

if not bases_df.empty:
    select_base = st.selectbox("选择要编辑的基地", options=bases_df["base_code"].tolist())
    selected_base_row = bases_df[bases_df["base_code"] == select_base].iloc[0]

    with st.form("base_update_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            edit_code = st.text_input("基地编号", value=selected_base_row["base_code"], disabled=True)
        with c2:
            edit_name = st.text_input("基地名称", value=selected_base_row["base_name"])
        with c3:
            edit_admin = st.text_input("县级行政区代码", value=selected_base_row.get("admin_code", ""))
        edit_remarks = st.text_area("备注", value=selected_base_row.get("remarks", ""), height=80)
        update_btn = st.form_submit_button("💾 保存修改", type="primary", use_container_width=True)

        if update_btn:
            try:
                from wheat_app.repositories.experiment_repository import update_experiment_base
                update_experiment_base(
                    base_code=select_base,
                    base_name=edit_name.strip(),
                    admin_code=edit_admin.strip() or edit_code[:6],
                    remarks=edit_remarks.strip(),
                )
                st.success(f"✅ 基地 {select_base} 已更新。")
                st.rerun()
            except Exception as exc:
                st.error(f"更新失败：{exc}")

st.markdown("---")
st.markdown("### 📋 现有基地列表")

if bases_df.empty:
    st.info("暂无试验基地，先创建一个基地再继续管理小区。")
else:
    display = bases_df.copy()
    display["小区数量"] = display["base_code"].map(
        lambda code: int((plots_df["base_code"] == code).sum()) if "base_code" in plots_df.columns else 0
    )
    st.dataframe(display, width='stretch', hide_index=True)

    st.markdown("### 🗑️ 删除基地")
    selected_delete = st.selectbox("选择要删除的基地", options=bases_df["base_code"].tolist(), key="delete_base_select")
    if st.button("删除选中基地", type="secondary", use_container_width=True):
        try:
            delete_experiment_base(selected_delete)
            st.success(f"✅ 基地 {selected_delete} 已删除。")
            st.rerun()
        except Exception as exc:
            st.error(f"删除失败：{exc}")
