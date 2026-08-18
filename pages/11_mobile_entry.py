# -*- coding: utf-8 -*-
"""手机端扫码录入页面 — 扫描二维码后的落地页"""

import requests
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="田间数据采集", page_icon="📱", layout="centered")

# ---- 从 URL 参数或 Streamlit 配置获取 API 地址 ----
params = st.query_params
# 优先使用 URL 参数传入的 API 地址（二维码编码时写入）
api_base_param = params.get("api", None)
# 否则使用 Streamlit 配置的服务器地址
if api_base_param:
    API_BASE = api_base_param.rstrip("/")
else:
    # 从 Streamlit 服务器地址推导
    hostname = st.get_option("server.address") or "localhost"
    port = st.get_option("server.port") or 8501
    # 如果是 localhost，假设后端在 8001；否则用同主机 8001
    API_BASE = f"http://{hostname}:8001"

# ---- 获取 URL 参数 ----
plot_param = params.get("plot", params.get("plot_code", None))

if not plot_param:
    st.error("缺少小区参数，请通过扫描二维码进入")
    st.stop()

# ---- 会话状态 ----
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "plot_info" not in st.session_state:
    st.session_state.plot_info = None


def api_get(endpoint, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        st.error(f"API 请求失败: {e}")
        return None


def api_post(endpoint, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.post(f"{API_BASE}{endpoint}", json=data, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            st.error(f"提交失败: {detail}")
            return None
    except Exception as e:
        st.error(f"API 请求失败: {e}")
        return None


# ---- 获取小区信息（支持 plot_code 和 plot_id 两种方式）----
if st.session_state.plot_info is None:
    plot_data = None
    # 尝试作为 plot_code 查询（如 "Ⅰ-CK"）
    plot_data = api_get(f"/api/v1/plots/{plot_param}")

    # 如果失败，尝试作为 ID 查询（兼容旧版二维码）
    if plot_data is None:
        try:
            plot_id_num = int(plot_param)
            plot_data = api_get(f"/api/v1/plots/by-id/{plot_id_num}")
        except ValueError:
            pass

    if plot_data:
        st.session_state.plot_info = plot_data

plot_info = st.session_state.plot_info
if not plot_info:
    st.error(f"找不到小区：{plot_param}")
    st.stop()

plot_id = plot_info.get("id")
plot_code = plot_info.get("plot_code", "")
block = plot_info.get("block", "")
treatment = plot_info.get("treatment", "")
trt_name = plot_info.get("treatment_name", treatment)

# ---- 页面标题 ----
st.title("田间数据采集")
st.markdown(f"""
<div style="background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:15px;border-radius:10px;margin-bottom:15px;">
    <h3 style="margin:0;">{plot_code}</h3>
    <p style="margin:5px 0 0;">区组: {block} | 处理: {treatment} ({trt_name})</p>
</div>
""", unsafe_allow_html=True)

# 显示 API 地址（调试用）
with st.expander("API 连接信息", expanded=False):
    st.caption(f"后端 API: `{API_BASE}`")

# ---- 登录/用户信息 ----
if not st.session_state.auth_token:
    st.markdown("### 登录")
    with st.form("login_form"):
        username = st.text_input("用户名", placeholder="请输入用户名")
        password = st.text_input("密码", type="password", placeholder="请输入密码")
        submitted = st.form_submit_button("登录", use_container_width=True)
        if submitted:
            result = api_post("/api/v1/auth/login", {
                "username": username,
                "password": password,
            })
            if result and "access_token" in result:
                st.session_state.auth_token = result["access_token"]
                st.session_state.current_user = {
                    "user_id": result.get("user_id"),
                    "username": result.get("username"),
                    "real_name": result.get("real_name"),
                    "role": result.get("role"),
                }
                st.success(f"欢迎，{result.get('real_name') or result.get('username')}！")
                st.rerun()
else:
    user = st.session_state.current_user
    st.markdown(f"""
    <div style="background:#d4edda;padding:10px;border-radius:8px;border:1px solid #c3e6cb;margin-bottom:15px;">
        <b>{user['real_name'] or user['username']}</b>
        <span style="float:right;color:#888;font-size:12px;">角色: {user['role']}</span>
    </div>
    """, unsafe_allow_html=True)
    if st.button("退出登录", use_container_width=True):
        st.session_state.auth_token = None
        st.session_state.current_user = None
        st.rerun()

# ---- 数据录入 ----
if st.session_state.auth_token:
    token = st.session_state.auth_token

    st.markdown("---")
    st.markdown("### 数据录入")

    tabs = st.tabs(["土壤数据", "物候期", "出苗调查",
                    "农艺性状", "生理指标", "产量数据", "品质数据"])

    # ---- 土壤 ----
    with tabs[0]:
        st.markdown(f"#### {plot_code} - 土壤数据")
        phase = st.selectbox("测定阶段", ["播前", "收获后"], key="soil_phase")
        with st.form("soil_form"):
            col1, col2 = st.columns(2)
            with col1:
                ph = st.number_input("pH 值", min_value=0.0, max_value=14.0, step=0.1, key="soil_ph")
                fe_available = st.number_input("有效铁 (mg/kg)", min_value=0.0, step=0.01, key="soil_fe")
                organic_matter = st.number_input("有机质 (g/kg)", min_value=0.0, step=0.01, key="soil_om")
            with col2:
                fe_total = st.number_input("全铁 (g/kg)", min_value=0.0, step=0.01, key="soil_fe_total")
                p_available = st.number_input("有效磷 (mg/kg)", min_value=0.0, step=0.01, key="soil_p")
                k_available = st.number_input("有效钾 (mg/kg)", min_value=0.0, step=0.01, key="soil_k")
            submitted = st.form_submit_button("提交土壤数据", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id, "phase": phase,
                    "ph": ph, "fe_available": fe_available, "fe_total": fe_total,
                    "organic_matter": organic_matter, "p_available": p_available,
                    "k_available": k_available,
                }
                result = api_post("/api/v1/data/soil", data, token)
                if result:
                    st.success("土壤数据提交成功！")

    # ---- 物候期（字段与 Phenology 模型对齐）----
    with tabs[1]:
        st.markdown(f"#### {plot_code} - 物候期")
        with st.form("phenology_form"):
            col1, col2 = st.columns(2)
            with col1:
                sowing = st.date_input("播种日期", key="phen_sowing")
                emergence = st.date_input("出苗日期", key="phen_emergence")
                jointing = st.date_input("拔节日期", key="phen_jointing")
                regreening = st.date_input("返青日期", key="phen_regreening")
            with col2:
                heading = st.date_input("抽穗日期", key="phen_heading")
                flowering = st.date_input("开花日期", key="phen_flowering")
                filling = st.date_input("灌浆日期", key="phen_filling")
                maturity = st.date_input("成熟日期", key="phen_maturity")
            submitted = st.form_submit_button("提交物候期数据", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id,
                    "sowing": str(sowing) if sowing else None,
                    "emergence": str(emergence) if emergence else None,
                    "regreening": str(regreening) if regreening else None,
                    "jointing": str(jointing) if jointing else None,
                    "heading": str(heading) if heading else None,
                    "flowering": str(flowering) if flowering else None,
                    "filling": str(filling) if filling else None,
                    "maturity": str(maturity) if maturity else None,
                }
                if api_post("/api/v1/data/phenology", data, token):
                    st.success("物候期数据提交成功！")

    # ---- 出苗调查（字段与 Emergence 模型对齐）----
    with tabs[2]:
        st.markdown(f"#### {plot_code} - 出苗调查")
        with st.form("emergence_form"):
            col1, col2 = st.columns(2)
            with col1:
                seeds_sown = st.number_input("播种粒数", min_value=0, step=1, key="em_sown")
                emerged_7d = st.number_input("7天出苗数", min_value=0, step=1, key="em_em7d")
                emerged_14d = st.number_input("14天出苗数", min_value=0, step=1, key="em_em14d")
            with col2:
                rate_7d = st.number_input("7天出苗率(%)", min_value=0.0, max_value=100.0, step=0.1, key="em_rate7d")
                rate_14d = st.number_input("14天出苗率(%)", min_value=0.0, max_value=100.0, step=0.1, key="em_rate14d")
                basic_seedlings = st.number_input("基本苗数(万/亩)", min_value=0.0, step=0.1, key="em_basic")
            submitted = st.form_submit_button("提交出苗数据", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id,
                    "seeds_sown": seeds_sown,
                    "emerged_7d": emerged_7d,
                    "rate_7d": rate_7d,
                    "emerged_14d": emerged_14d,
                    "rate_14d": rate_14d,
                    "basic_seedlings": basic_seedlings,
                }
                if api_post("/api/v1/data/emergence", data, token):
                    st.success("出苗数据提交成功！")

    # ---- 农艺性状（字段与 AgronomicTraits 模型对齐）----
    with tabs[3]:
        st.markdown(f"#### {plot_code} - 农艺性状")
        with st.form("agronomic_form"):
            col1, col2 = st.columns(2)
            with col1:
                tillers_prewinter = st.number_input("越冬前分蘖(个/株)", min_value=0.0, step=0.1, key="ag_tiller_pre")
                tillers_postregreen = st.number_input("返青后分蘖(个/株)", min_value=0.0, step=0.1, key="ag_tiller_post")
                tillers_jointing = st.number_input("拔节期分蘖(个/株)", min_value=0.0, step=0.1, key="ag_tiller_joint")
                plant_height = st.number_input("株高 (cm)", min_value=0.0, step=0.1, key="ag_height")
            with col2:
                lai_jointing = st.number_input("拔节期LAI", min_value=0.0, step=0.01, key="ag_lai_joint")
                lai_heading = st.number_input("抽穗期LAI", min_value=0.0, step=0.01, key="ag_lai_head")
                dry_weight_jointing = st.number_input("拔节期干重(g/株)", min_value=0.0, step=0.1, key="ag_dw_joint")
                dry_weight_heading = st.number_input("抽穗期干重(g/株)", min_value=0.0, step=0.1, key="ag_dw_head")
            col3, col4 = st.columns(2)
            with col3:
                dry_weight_maturity = st.number_input("成熟期干重(g/株)", min_value=0.0, step=0.1, key="ag_dw_mat")
            with col4:
                root_dry_weight = st.number_input("根系干重(g/株)", min_value=0.0, step=0.1, key="ag_root")
            submitted = st.form_submit_button("提交农艺性状", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id,
                    "tillers_prewinter": tillers_prewinter,
                    "tillers_postregreen": tillers_postregreen,
                    "tillers_jointing": tillers_jointing,
                    "plant_height": plant_height,
                    "lai_jointing": lai_jointing,
                    "lai_heading": lai_heading,
                    "dry_weight_jointing": dry_weight_jointing,
                    "dry_weight_heading": dry_weight_heading,
                    "dry_weight_maturity": dry_weight_maturity,
                    "root_dry_weight": root_dry_weight,
                }
                if api_post("/api/v1/data/agronomic", data, token):
                    st.success("农艺性状提交成功！")

    # ---- 生理指标（字段与 Physiological 模型对齐）----
    with tabs[4]:
        st.markdown(f"#### {plot_code} - 生理指标")
        with st.form("physiological_form"):
            col1, col2 = st.columns(2)
            with col1:
                spad_jointing = st.number_input("拔节期SPAD", min_value=0.0, step=0.1, key="phys_spad_joint")
                spad_heading = st.number_input("抽穗期SPAD", min_value=0.0, step=0.1, key="phys_spad_head")
                spad_filling = st.number_input("灌浆期SPAD", min_value=0.0, step=0.1, key="phys_spad_fill")
                photo_rate_heading = st.number_input("抽穗期光合速率", min_value=0.0, step=0.01, key="phys_photo_head")
            with col2:
                photo_rate_filling = st.number_input("灌浆期光合速率", min_value=0.0, step=0.01, key="phys_photo_fill")
                active_fe_jointing = st.number_input("拔节期活性铁", min_value=0.0, step=0.01, key="phys_fe_joint")
                active_fe_filling = st.number_input("灌浆期活性铁", min_value=0.0, step=0.01, key="phys_fe_fill")
            col3, col4 = st.columns(2)
            with col3:
                cat = st.number_input("CAT活性", min_value=0.0, step=0.01, key="phys_cat")
            with col4:
                pod = st.number_input("POD活性", min_value=0.0, step=0.01, key="phys_pod")
            submitted = st.form_submit_button("提交生理指标", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id,
                    "spad_jointing": spad_jointing,
                    "spad_heading": spad_heading,
                    "spad_filling": spad_filling,
                    "photo_rate_heading": photo_rate_heading,
                    "photo_rate_filling": photo_rate_filling,
                    "active_fe_jointing": active_fe_jointing,
                    "active_fe_filling": active_fe_filling,
                    "cat": cat,
                    "pod": pod,
                }
                if api_post("/api/v1/data/physiological", data, token):
                    st.success("生理指标提交成功！")

    # ---- 产量数据（字段与 YieldData 模型对齐）----
    with tabs[5]:
        st.markdown(f"#### {plot_code} - 产量数据")
        with st.form("yield_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                spikes_per_mu = st.number_input("亩穗数 (万穗/亩)", min_value=0.0, step=0.1, key="yld_spikes")
            with col2:
                grains_per_spike = st.number_input("穗粒数 (粒/穗)", min_value=0.0, step=0.1, key="yld_grains")
            with col3:
                thousand_grain_wt_1 = st.number_input("千粒重第1组 (g)", min_value=0.0, step=0.01, key="yld_tkw1")
            col4, col5, col6 = st.columns(3)
            with col4:
                thousand_grain_wt_2 = st.number_input("千粒重第2组 (g)", min_value=0.0, step=0.01, key="yld_tkw2")
            with col5:
                actual_yield = st.number_input("实际产量 (kg/亩)", min_value=0.0, step=0.1, key="yld_actual")
            with col6:
                harvest_index = st.number_input("收获指数", min_value=0.0, max_value=1.0, step=0.01, key="yld_hi")

            # 自动计算理论产量
            if spikes_per_mu and grains_per_spike:
                tgw_vals = [v for v in [thousand_grain_wt_1, thousand_grain_wt_2] if v]
                if tgw_vals:
                    tgw_avg = sum(tgw_vals) / len(tgw_vals)
                    theoretical_yield = round(spikes_per_mu * grains_per_spike * tgw_avg / 100, 1)
                    st.info(f"理论产量 = {spikes_per_mu} × {grains_per_spike} × {tgw_avg} / 100 = **{theoretical_yield} kg/亩**")

            submitted = st.form_submit_button("提交产量数据", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id,
                    "spikes_per_mu": spikes_per_mu,
                    "grains_per_spike": grains_per_spike,
                    "thousand_grain_wt_1": thousand_grain_wt_1,
                    "thousand_grain_wt_2": thousand_grain_wt_2,
                    "actual_yield": actual_yield,
                    "harvest_index": harvest_index,
                }
                # 计算理论产量
                if spikes_per_mu and grains_per_spike:
                    tgw_vals = [v for v in [thousand_grain_wt_1, thousand_grain_wt_2] if v]
                    if tgw_vals:
                        data["theoretical_yield"] = round(spikes_per_mu * grains_per_spike * (sum(tgw_vals) / len(tgw_vals)) / 100, 1)
                if api_post("/api/v1/data/yield", data, token):
                    st.success("产量数据提交成功！")

    # ---- 品质数据（字段与 QualityData 模型对齐）----
    with tabs[6]:
        st.markdown(f"#### {plot_code} - 品质数据")
        with st.form("quality_form"):
            col1, col2 = st.columns(2)
            with col1:
                grain_protein = st.number_input("籽粒蛋白质(%)", min_value=0.0, step=0.1, key="qual_prot")
                wet_gluten = st.number_input("湿面筋(%)", min_value=0.0, step=0.1, key="qual_glut")
            with col2:
                sds_sedimentation = st.number_input("SDS沉降值(mL)", min_value=0.0, step=0.1, key="qual_sds")
            col3, col4 = st.columns(2)
            with col3:
                grain_fe = st.number_input("籽粒铁含量(mg/kg)", min_value=0.0, step=0.1, key="qual_gfe")
            with col4:
                flour_fe = st.number_input("面粉铁含量(mg/kg)", min_value=0.0, step=0.1, key="qual_ffe")
            submitted = st.form_submit_button("提交品质数据", type="primary", use_container_width=True)
            if submitted:
                data = {
                    "plot_id": plot_id,
                    "grain_protein": grain_protein,
                    "wet_gluten": wet_gluten,
                    "sds_sedimentation": sds_sedimentation,
                    "grain_fe": grain_fe,
                    "flour_fe": flour_fe,
                }
                if api_post("/api/v1/data/quality", data, token):
                    st.success("品质数据提交成功！")

    # ---- 数据查询 ----
    st.markdown("---")
    if st.button("查看该小区已提交数据", use_container_width=True):
        st.markdown("### 数据查询")
        for tbl_key, tbl_label in [("soil", "土壤数据"), ("phenology", "物候期"),
                                   ("emergence", "出苗调查"), ("agronomic", "农艺性状"),
                                   ("physiological", "生理指标"), ("yield", "产量数据"),
                                   ("quality", "品质数据")]:
            data = api_get(f"/api/v1/data/{tbl_key}/{plot_code}", token)
            if data and (isinstance(data, list) and len(data) > 0 or data is not None):
                count = len(data) if isinstance(data, list) else 1
                st.markdown(f"**{tbl_label}**: 已提交 {count} 条")
            else:
                st.markdown(f"**{tbl_label}**: 暂无数据")

st.markdown("---")
st.markdown("""
<div style="text-align:center;color:#999;font-size:12px;">
    纳米铁肥小麦试验数据采集系统 | 数据提交后自动记录操作日志
</div>
""", unsafe_allow_html=True)
