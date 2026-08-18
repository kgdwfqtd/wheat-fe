# -*- coding: utf-8 -*-
"""常量定义 & 工具函数"""

import io
import base64

import qrcode

# ============================================================
# 处理定义 — fe_total 统一为 float，单位另存
# ============================================================
TREATMENTS = [
    {"code": "CK",     "name": "空白对照",       "color": "#E8E8E8", "fe_total": 0.0,   "fe_unit": "g/亩"},
    {"code": "FS",     "name": "硫酸亚铁对照",   "color": "#DAE8FC", "fe_total": 2000.0, "fe_unit": "g/亩"},  # 2.0 kg/亩 = 2000 g/亩
    {"code": "NF-0.5", "name": "纳米铁 半量",    "color": "#E1F5D5", "fe_total": 0.5,    "fe_unit": "g/亩"},
    {"code": "NF-1.0", "name": "纳米铁 标准量",  "color": "#D5E8D4", "fe_total": 1.0,    "fe_unit": "g/亩"},
    {"code": "NF-1.5", "name": "纳米铁 1.5倍量", "color": "#C8E6C9", "fe_total": 1.5,    "fe_unit": "g/亩"},
    {"code": "NF-2.0", "name": "纳米铁 2倍量",   "color": "#A5D6A7", "fe_total": 2.0,    "fe_unit": "g/亩"},
]

TREATMENT_CODES = [t["code"] for t in TREATMENTS]
TREATMENT_COLORS = {t["code"]: t["color"] for t in TREATMENTS}
TREATMENT_NAMES = {t["code"]: t["name"] for t in TREATMENTS}
TREATMENT_FE_TOTAL = {t["code"]: t["fe_total"] for t in TREATMENTS}
TREATMENT_FE_UNIT = {t["code"]: t["fe_unit"] for t in TREATMENTS}

BLOCKS = ["Ⅰ", "Ⅱ", "Ⅲ"]

# ============================================================
# 纳米铁各时期分配比例
# ============================================================
NF_SPLIT = {
    "拌种": 0.50,
    "拔节": 0.30,
    "灌浆": 0.20,
}

# 纳米铁亩用量 → 每小区用量系数（20 m² = 0.03 亩）
PLOT_RATIO = 0.03


def get_nf_plot_dose(treatment_code, stage=None):
    """获取某处理某时期的纳米铁小区用量(g)。
    仅对 NF- 系列处理有效；FS/CK 返回 0。
    """
    total = TREATMENT_FE_TOTAL.get(treatment_code, 0)
    if not isinstance(total, (int, float)) or total <= 0 or not treatment_code.startswith("NF-"):
        return 0.0
    if stage and stage in NF_SPLIT:
        return round(total * NF_SPLIT[stage] * PLOT_RATIO, 6)
    return round(total * PLOT_RATIO, 6)


# ============================================================
# 操作类型
# ============================================================
OP_TYPES = [
    "拌种", "拔节期喷施", "灌浆期喷施",
    "播种", "灌溉", "施肥（基肥）",
    "除草", "病虫害防治", "取样", "调查/测定", "其他",
]

# ============================================================
# 天气选项
# ============================================================
WEATHER_OPTIONS = ["晴", "多云", "阴", "小雨", "中雨", "大雨", "雾", "雪", "大风"]


# ============================================================
# 工具函数
# ============================================================
def make_plot_code(block, treatment):
    """生成小区编号，如 Ⅰ-CK"""
    return f"{block}-{treatment}"


def generate_qr_code(plot_code, base_url, api_base=None, box_size=10, border=4):
    """生成二维码，返回 (png_bytes, base64_string, qr_url)
    api_base: 后端 API 地址，手机端扫码后使用
    """
    qr_url = f"{base_url}/mobile_entry?plot={plot_code}"
    if api_base:
        # URL encode the api_base parameter
        from urllib.parse import urlencode
        qr_url += f"&{urlencode({'api': api_base})}"
    qr = qrcode.QRCode(version=1, box_size=box_size, border=border)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    img_b64 = base64.b64encode(png_bytes).decode()
    return png_bytes, img_b64, qr_url


def setup_sidebar():
    """渲染自定义中文侧边栏导航（默认英文导航已由 config.toml 禁用）"""
    import streamlit as st

    st.sidebar.title("🌾 纳米铁肥小麦试验")
    st.sidebar.caption("数据记录管理系统")

    st.sidebar.markdown("---")
    st.sidebar.page_link("app.py", label="首页仪表盘", icon="🏠")
    st.sidebar.page_link("pages/01_plots.py", label="小区管理", icon="📋")

    st.sidebar.markdown("---")
    st.sidebar.caption("📝 数据录入")
    st.sidebar.page_link("pages/02_soil.py", label="土壤数据", icon="🪣")
    st.sidebar.page_link("pages/03_phenology.py", label="物候期 & 出苗", icon="📅")
    st.sidebar.page_link("pages/04_agronomic.py", label="农艺性状", icon="🌱")
    st.sidebar.page_link("pages/05_physiological.py", label="生理指标", icon="🔬")
    st.sidebar.page_link("pages/06_yield.py", label="产量数据", icon="🌾")
    st.sidebar.page_link("pages/07_quality.py", label="品质数据", icon="🏆")

    st.sidebar.markdown("---")
    st.sidebar.caption("📊 数据管理")
    st.sidebar.page_link("pages/08_operations.py", label="操作日志", icon="📝")
    st.sidebar.page_link("pages/09_export.py", label="数据导出 & 图表", icon="📥")

    st.sidebar.markdown("---")
    st.sidebar.caption("📱 移动端")
    st.sidebar.page_link("pages/10_qrcode.py", label="二维码生成", icon="📱")


# ============================================================
# 数据库列名 → 中文显示名映射
# ============================================================
COLUMN_NAME_MAP = {
    "plot_code": "小区编号",
    "block": "区组",
    "treatment": "处理",
    "area_m2": "面积(m²)",
    "field_name": "田块",
    "phase": "测定阶段",
    "ph": "pH",
    "fe_available": "有效铁(mg/kg)",
    "fe_total": "全铁(g/kg)",
    "organic_matter": "有机质(g/kg)",
    "p_available": "有效磷(mg/kg)",
    "k_available": "速效钾(mg/kg)",
    "cec": "CEC(cmol/kg)",
    "bulk_density": "容重(g/cm³)",
    "sowing": "播种期",
    "emergence": "出苗期",
    "tillering": "分蘖期",
    "overwinter": "越冬期",
    "regreening": "返青期",
    "jointing": "拔节期",
    "heading": "抽穗期",
    "flowering": "开花期",
    "filling": "灌浆期",
    "maturity": "成熟期",
    "seeds_sown": "播种粒数",
    "emerged_7d": "7天出苗数",
    "rate_7d": "7天出苗率(%)",
    "emerged_14d": "14天出苗数",
    "rate_14d": "14天出苗率(%)",
    "basic_seedlings": "基本苗数",
    "tillers_prewinter": "越冬前分蘖(个/株)",
    "tillers_postregreen": "返青后分蘖(个/株)",
    "tillers_jointing": "拔节期分蘖(个/株)",
    "plant_height": "株高(cm)",
    "lai_jointing": "拔节期LAI",
    "lai_heading": "抽穗期LAI",
    "dry_weight_jointing": "拔节期干重(g/株)",
    "dry_weight_heading": "抽穗期干重(g/株)",
    "dry_weight_maturity": "成熟期干重(g/株)",
    "root_dry_weight": "根系干重(g/株)",
    "spad_jointing": "拔节期SPAD",
    "spad_heading": "抽穗期SPAD",
    "spad_filling": "灌浆期SPAD",
    "photo_rate_heading": "抽穗期光合速率",
    "photo_rate_filling": "灌浆期光合速率",
    "active_fe_jointing": "拔节期活性铁",
    "active_fe_filling": "灌浆期活性铁",
    "cat": "CAT活性",
    "pod": "POD活性",
    "spikes_per_mu": "亩穗数(万穗/亩)",
    "grains_per_spike": "穗粒数(粒/穗)",
    "thousand_grain_wt_1": "千粒重第1组(g)",
    "thousand_grain_wt_2": "千粒重第2组(g)",
    "theoretical_yield": "理论产量(kg/亩)",
    "actual_yield": "实际产量(kg/亩)",
    "harvest_index": "收获指数",
    "grain_protein": "籽粒蛋白质(%)",
    "wet_gluten": "湿面筋(%)",
    "sds_sedimentation": "SDS沉降值(mL)",
    "grain_fe": "籽粒铁含量(mg/kg)",
    "flour_fe": "面粉铁含量(mg/kg)",
    "date": "日期",
    "time": "时间",
    "op_type": "操作类型",
    "dosage": "用量/参数",
    "weather": "天气",
    "temperature": "温度(℃)",
    "humidity": "湿度(%)",
    "operator": "操作人",
    "remarks": "备注",
}


def rename_columns_cn(df):
    """将 DataFrame 英文列名替换为中文显示名"""
    return df.rename(columns=COLUMN_NAME_MAP)
