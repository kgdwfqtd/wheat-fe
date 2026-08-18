# -*- coding: utf-8 -*-
"""二维码生成页面 — 为每个试验小区生成手机扫码入口"""

import io
import zipfile
import base64
import streamlit as st
import pandas as pd
from wheat_app.repositories.experiment_repository import get_all_plots
from utils import TREATMENT_NAMES, BLOCKS, generate_qr_code, setup_sidebar

st.set_page_config(page_title="二维码生成", page_icon="📱", layout="wide")
setup_sidebar()

st.title("📱 试验小区二维码生成")
st.caption("扫描二维码可在手机端快速进入对应小区的数据录入页面")

# ---- 服务器 IP ----
st.markdown("### ⚙️ 服务器地址设置")
st.caption("请填写手机可访问的电脑局域网 IP，手机需与电脑在同一 WiFi 下")

col1, col2 = st.columns([2, 1])
with col1:
    default_ip = st.session_state.get("server_ip", "192.168.1.11")
    server_ip = st.text_input("电脑局域网 IP 地址", value=default_ip,
                              help="在 cmd 中运行 ipconfig 查看 WLAN 的 IPv4 地址")
with col2:
    port = st.number_input("前端端口", value=8501, disabled=True)

base_url = f"http://{server_ip}:{port}"
st.info(f"手机访问基础地址：`{base_url}`")
st.session_state["server_ip"] = server_ip

# 计算后端 API 地址（用于二维码编码）
api_base_url = f"http://{server_ip}:8001"
st.info(f"后端 API 地址：`{api_base_url}`")

# ---- 小区数据 ----
plots_df = get_all_plots()
if plots_df.empty:
    st.warning("暂无小区数据，请先在「小区管理」中初始化。")
    st.stop()

# ---- 单/批量 tab ----
st.markdown("---")
st.markdown("### 📲 二维码操作")

tab_single, tab_batch = st.tabs(["🔍 单个二维码", "📦 批量生成全部"])

with tab_single:
    st.markdown("选择一个小区生成二维码")
    col_sel1, col_sel2 = st.columns([1, 2])
    with col_sel1:
        selected_block = st.selectbox("选择区组", BLOCKS)
    with col_sel2:
        block_plots = plots_df[plots_df["block"] == selected_block]
        plot_options = block_plots["plot_code"].tolist()
        selected_plot = st.selectbox("选择小区", plot_options)

    if st.button("🔖 生成二维码", type="primary", use_container_width=True):
        row = plots_df[plots_df["plot_code"] == selected_plot].iloc[0]
        plot_id = int(row["id"])
        plot_code = row["plot_code"]
        treatment = row["treatment"]
        block = row["block"]

        png_bytes, img_b64, qr_url = generate_qr_code(plot_code, base_url, api_base=api_base_url, box_size=10, border=4)

        st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{img_b64}" width="300"/></div>',
                    unsafe_allow_html=True)

        trt_name = TREATMENT_NAMES.get(treatment, "")
        st.markdown(f"""
        <div style="background:#f0f7ff;padding:15px;border-radius:8px;border:1px solid #b3d4ff;margin-top:10px;">
            <h4 style="margin:0;color:#1a5276;">🏷️ 小区信息</h4>
            <p style="margin:8px 0;color:#333;">
                <b>小区编号：</b>{plot_code} &nbsp;|&nbsp;
                <b>区组：</b>{block} &nbsp;|&nbsp;
                <b>处理：</b>{treatment} ({trt_name})
            </p>
            <p style="margin:4px 0;color:#666;font-size:12px;">
                📱 扫码 URL: <code>{qr_url}</code>
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.download_button(
            label="💾 下载二维码 PNG",
            data=png_bytes,
            file_name=f"QR_{plot_code}.png",
            mime="image/png",
            use_container_width=True,
        )

with tab_batch:
    st.markdown("一键生成所有小区的二维码，可打印后张贴到田间对应小区")

    col_batch1, col_batch2 = st.columns([1, 1])
    with col_batch1:
        include_all = st.checkbox("包含全部 18 个小区", value=True)
        if not include_all:
            sel_blocks = st.multiselect("选择区组", BLOCKS, default=BLOCKS)
        else:
            sel_blocks = BLOCKS

    filtered = plots_df if include_all else plots_df[plots_df["block"].isin(sel_blocks)]

    if st.button("🔖 生成全部二维码", type="primary", use_container_width=True):
        results = []
        for _, row in filtered.iterrows():
            plot_id = int(row["id"])
            plot_code = row["plot_code"]
            treatment = row["treatment"]
            block = row["block"]

            png_bytes, img_b64, qr_url = generate_qr_code(plot_code, base_url, api_base=api_base_url, box_size=8, border=3)
            trt_name = TREATMENT_NAMES.get(treatment, "")
            results.append({
                "plot_code": plot_code,
                "block": block,
                "treatment": treatment,
                "trt_name": trt_name,
                "url": qr_url,
                "img_b64": img_b64,
                "png_bytes": png_bytes,
            })

        # 按区组分组显示
        st.markdown("#### 🖨️ 二维码预览（可直接打印）")
        for block in BLOCKS:
            block_results = [r for r in results if r["block"] == block]
            if not block_results:
                continue
            st.markdown(f"**区组 {block}**")
            cols = st.columns(3)
            for i, r in enumerate(block_results):
                with cols[i % 3]:
                    st.markdown(f'''
                    <div style="border:1px solid #ddd;border-radius:8px;padding:10px;text-align:center;background:#fff;">
                        <img src="data:image/png;base64,{r['img_b64']}" width="140"/>
                        <div style="font-weight:bold;margin-top:6px;font-size:14px;">{r['plot_code']}</div>
                        <div style="color:#666;font-size:11px;">{r['treatment']} ({r['trt_name']})</div>
                    </div>
                    ''', unsafe_allow_html=True)

        # 打包下载
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for r in results:
                zf.writestr(f"QR_{r['plot_code']}.png", r["png_bytes"])
        zip_buf.seek(0)

        st.download_button(
            label="📦 打包下载全部二维码 (ZIP)",
            data=zip_buf.read(),
            file_name="all_qrcodes.zip",
            mime="application/zip",
            use_container_width=True,
        )

# ---- 使用说明 ----
st.markdown("---")
with st.expander("📖 使用说明"):
    st.markdown("""
    1. **确保手机和电脑在同一局域网**（连接同一个 WiFi）
    2. 在上方填入电脑的局域网 IP 地址（通过 `ipconfig` 查看 WLAN 的 IPv4）
    3. 选择单个或批量生成二维码
    4. 用手机浏览器或微信扫描二维码
    5. 首次使用需登录，登录后自动显示对应小区信息
    6. 所有数据通过加密传输，操作会被记录日志
    """)