# -*- coding: utf-8 -*-
"""通用表单渲染器 — 各数据录入页共享"""

import streamlit as st
from database import upsert_record, get_record, get_all_records, get_all_plots
from utils import setup_sidebar, rename_columns_cn


def render_data_entry_page(
    title: str,
    icon: str,
    table: str,
    field_defs: list[dict],
    extra_keys: dict | None = None,
    validators: dict | None = None,
):
    """渲染标准数据录入页面。

    参数:
        title: 页面标题
        icon: 页面图标
        table: 数据库表名
        field_defs: 字段定义列表，每个元素为 dict:
            {"key": str, "label": str, "step": float=0.1, "min": float=0.0, "max": float|None=None,
             "cols": int=2, "group": str|None=None}
        extra_keys: 复合键字典（如 {"phase": "播前"}），用于 soil_data
        validators: 校验器 dict，key 为字段名，value 为 callable(value) -> (ok, warning_msg)
    """
    setup_sidebar()
    st.set_page_config(page_title=title, page_icon=icon)
    st.title(f"{icon} {title}")

    plots_df = get_all_plots()
    plot_options = plots_df["plot_code"].tolist()

    # ---- 小区选择 ----
    st.markdown("### 📝 录入 / 编辑")
    selected_plot = st.selectbox("选择小区", options=plot_options)

    # 复合键选择（如 soil_data 的 phase）
    extra_vals = {}
    if extra_keys:
        extra_cols = st.columns(len(extra_keys))
        for i, (key, choices) in enumerate(extra_keys.items()):
            with extra_cols[i]:
                extra_vals[key] = st.selectbox(
                    f"**{key}**",
                    options=list(choices),
                    key=f"extra_{key}"
                )

    plot_info = plots_df[plots_df["plot_code"] == selected_plot]
    if plot_info.empty:
        st.warning("请先在「小区管理」中初始化小区。")
        return

    plot_id = int(plot_info.iloc[0]["id"])
    existing = get_record(table, plot_id, extra_keys=extra_vals if extra_vals else None)

    # ---- 表单 ----
    with st.form(f"{table}_form"):
        st.caption(f"当前小区：{selected_plot}")

        # 按 group 分组渲染字段
        grouped = {}
        no_group = []
        for fd in field_defs:
            grp = fd.get("group")
            if grp:
                grouped.setdefault(grp, []).append(fd)
            else:
                no_group.append(fd)

        inputs = {}

        def _render_field(fd: dict):
            """渲染单个字段"""
            key = fd["key"]
            label = fd["label"]
            step = fd.get("step", 0.1)
            vmin = fd.get("min", 0.0)
            vmax = fd.get("max", None)
            ex_val = existing.get(key) if existing else None
            inputs[key] = st.number_input(
                label, value=ex_val,
                step=step, min_value=vmin, max_value=vmax
            )

        # 分组渲染
        all_sections = []
        for grp_name, fds in grouped.items():
            all_sections.append((grp_name, fds))
        if no_group:
            all_sections.append(("", no_group))

        for grp_name, fds in all_sections:
            if grp_name:
                st.markdown(f"**{grp_name}**")
            cols_per_row = fds[0].get("cols", 2) if fds else 2
            for i in range(0, len(fds), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(fds):
                        with cols[j]:
                            _render_field(fds[i + j])

        submitted = st.form_submit_button("💾 保存", type="primary", width='stretch')

        if submitted:
            data = {}
            warnings = []
            for fd in field_defs:
                key = fd["key"]
                val = inputs.get(key)
                if val is not None:
                    # 校验
                    if validators and key in validators:
                        ok, msg = validators[key](val)
                        if not ok:
                            warnings.append(msg)
                    data[key] = val

            if warnings:
                for w in warnings:
                    st.warning(w)
            if data:
                upsert_record(table, plot_id, data, extra_keys=extra_vals if extra_vals else None)
                st.success(f"✅ {selected_plot} 数据已保存！")
                st.rerun()
            elif not warnings:
                st.error("请至少填写一项数据。")

    # ---- 已录入数据表格 ----
    st.markdown("---")
    st.markdown("### 📊 已录入数据")
    df_all = get_all_records(table)
    if not df_all.empty:
        hide_cols = [c for c in df_all.columns if c in ['id']]
        df_display = rename_columns_cn(df_all.drop(columns=hide_cols, errors='ignore'))
        st.dataframe(df_display,
                     width='stretch', hide_index=True)
    else:
        st.info(f"暂无{title}数据。")
