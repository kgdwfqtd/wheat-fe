# -*- coding: utf-8 -*-
"""小区管理页面"""

import io
import zipfile
import streamlit as st
import pandas as pd
from wheat_app.repositories.experiment_repository import init_plots
from wheat_app.services.plot_service import (
    load_plots_data,
    build_plot_display_rows,
    build_qr_zip_for_block,
    build_qr_zip_for_all,
    get_layout_summary,
    reset_experiment_data,
)
from utils import (BLOCKS, TREATMENT_CODES, TREATMENT_NAMES, TREATMENT_COLORS,
                   setup_sidebar, generate_qr_code)

st.set_page_config(page_title="小区管理", page_icon="📋", layout="wide")
setup_sidebar()

st.title("📋 小区管理")

plots_df = load_plots_data()

if plots_df.empty:
    st.warning("尚未初始化小区数据，请点击下方按钮初始化。")
    if st.button("🔧 一键初始化 18 个小区", type="primary", width='stretch'):
        init_plots()
        st.rerun()
else:
    # ---- 服务器 IP 设置 ----
    with st.expander("⚙️ 二维码服务器地址设置（扫码进入手机端录入）", expanded=False):
        col1, col2 = st.columns([2, 1])
        with col1:
            default_ip = st.session_state.get("server_ip", "192.168.1.11")
            server_ip = st.text_input("电脑局域网 IP", value=default_ip,
                                      help="在 cmd 中运行 ipconfig 查看 WLAN 的 IPv4 地址")
        with col2:
            port = st.number_input("前端端口", value=8501, disabled=True)
        st.session_state["server_ip"] = server_ip
        base_url = f"http://{server_ip}:{port}"
        st.info(f"📱 手机访问基础地址：`{base_url}`")

    st.markdown("### 小区列表")
    display_df = build_plot_display_rows(plots_df)
    st.dataframe(display_df, width='stretch', hide_index=True)

    # ---- 按区组显示布局 + 二维码 ----
    st.markdown("---")
    st.markdown("### 🗺️ 田间布局 & 二维码")
    st.caption("点击区组下方的「生成二维码」按钮，可查看/下载对应小区的扫码录入二维码")

    default_ip = st.session_state.get("server_ip", "192.168.1.11")
    base_url = f"http://{default_ip}:8501"
    api_base_url = f"http://{default_ip}:8001"

    for block in BLOCKS:
        block_rows = get_layout_summary(plots_df, block, TREATMENT_CODES, TREATMENT_COLORS)

        # 布局行
        cols = st.columns(len(TREATMENT_CODES) + 1)
        cols[0].markdown(f"**区组 {block}**")
        for i, cell in enumerate(block_rows):
            code = cell["plot_code"]
            color = cell["color"]
            name = cell["name"]
            cols[i + 1].markdown(
                f'<div style="background:{color};padding:8px;border-radius:4px;'
                f'text-align:center;font-size:13px;border:1px solid #999;">'
                f'<b>{code}</b><br><small>{name}</small></div>',
                unsafe_allow_html=True
            )

        # 二维码区域
        with st.expander(f"📱 区组 {block} 二维码（点击展开）", expanded=False):
            st.markdown(f"**区组 {block}** — 共 {len(block_rows)} 个小区")
            qr_cols = st.columns(3)

            for i, cell in enumerate(block_rows):
                plot_code = cell["plot_code"]
                trt = cell["treatment"]
                png_bytes, img_b64, _ = generate_qr_code(plot_code, base_url, api_base=api_base_url, box_size=8, border=3)
                with qr_cols[i % 3]:
                    st.markdown(f'''
                    <div style="border:1px solid #ddd;border-radius:8px;padding:8px;text-align:center;background:#fff;margin-bottom:8px;">
                        <img src="data:image/png;base64,{img_b64}" width="120"/>
                        <div style="font-weight:bold;margin-top:4px;font-size:13px;">{plot_code}</div>
                        <div style="color:#666;font-size:11px;">{trt} ({TREATMENT_NAMES.get(trt, "")})</div>
                    </div>
                    ''', unsafe_allow_html=True)
                    st.download_button(
                        label=f"💾 {plot_code}",
                        data=png_bytes,
                        file_name=f"QR_{plot_code}.png",
                        mime="image/png",
                        key=f"dl_{block}_{plot_code}",
                        use_container_width=True,
                    )

            # 打包下载本区组
            zip_bytes = build_qr_zip_for_block(plots_df, block, base_url, api_base_url)
            st.download_button(
                label=f"📦 打包下载区组 {block} 全部二维码",
                data=zip_bytes,
                file_name=f"block_{block}_qrcodes.zip",
                mime="application/zip",
                key=f"zip_{block}",
                use_container_width=True,
            )

    # ---- 全部二维码打包下载 ----
    st.markdown("---")
    all_zip_bytes = build_qr_zip_for_all(plots_df, base_url, api_base_url)
    st.download_button(
        label="📦 打包下载全部 18 个小区二维码",
        data=all_zip_bytes,
        file_name="all_plots_qrcodes.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )

    # ---- 高级操作 ----
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