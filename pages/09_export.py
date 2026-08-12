# -*- coding: utf-8 -*-
"""数据导出 & 图表"""

import streamlit as st
import pandas as pd
import io
from datetime import date
from database import export_to_excel, get_all_records, get_completion_stats, backup_db
from utils import setup_sidebar, rename_columns_cn

st.set_page_config(page_title="数据导出 & 图表", page_icon="📥")
setup_sidebar()

st.title("📥 数据导出 & 图表分析")

# ============================================================
# Tab 1: 数据预览 & 导出
# ============================================================
tab1, tab2 = st.tabs(["📤 导出 Excel", "📊 图表分析"])

with tab1:
    st.markdown("### 📤 数据预览 & 导出为 Excel")

    table_options = {
        "soil_data": "土壤数据", "phenology": "物候期", "emergence": "出苗调查",
        "agronomic_traits": "农艺性状", "physiological": "生理指标",
        "yield_data": "产量数据", "quality_data": "品质数据", "operation_log": "操作日志",
    }
    selected_table = st.selectbox("选择数据表预览", options=list(table_options.keys()),
                                   format_func=lambda x: table_options[x])

    df_preview = get_all_records(selected_table)
    if df_preview is not None and not df_preview.empty:
        id_cols = [c for c in df_preview.columns if c == 'id' or c == 'plot_id']
        df_display = rename_columns_cn(df_preview.drop(columns=[c for c in id_cols if c in df_preview.columns], errors='ignore'))
        st.dataframe(df_display, width='stretch', hide_index=True)
        st.caption(f"共 {len(df_display)} 条记录")
    else:
        st.info("该表暂无数据。")

    st.markdown("---")
    st.markdown("### 💾 一键导出 Excel")

    today = date.today().strftime("%Y%m%d")
    default_name = f"纳米铁肥小麦试验数据_{today}.xlsx"

    if st.button("📥 导出全部数据为 Excel", type="primary", width='stretch'):
        # 用内存字节流，不写磁盘残留
        buf = io.BytesIO()
        export_to_excel(buf)
        buf.seek(0)
        # 同时自动备份
        bak = backup_db()
        st.success(f"✅ 数据已导出（备份：{bak}）")
        st.download_button(
            label="⬇️ 下载 Excel 文件",
            data=buf,
            file_name=default_name,
            mime="application/vnd.openxmlformats-officedocument-spreadsheetml.sheet",
            width='stretch',
        )

    # 空白模板导出（同样用内存流）
    st.markdown("---")
    st.markdown("### 📋 导出空白记录表模板")
    if st.button("📋 生成空白记录表", width='stretch'):
        with io.BytesIO() as tpl_buf:
            with pd.ExcelWriter(tpl_buf, engine="openpyxl") as writer:
                headers_map = {
                    "土壤数据": ["区组", "处理", "阶段", "pH", "有效铁(mg/kg)", "全铁(g/kg)",
                               "有机质(g/kg)", "有效磷(mg/kg)", "速效钾(mg/kg)", "CEC(cmol/kg)", "容重(g/cm³)"],
                    "物候期": ["区组", "处理", "播种", "出苗", "分蘖", "越冬", "返青", "拔节", "抽穗", "开花", "灌浆", "成熟"],
                    "出苗调查": ["区组", "处理", "播种粒数", "出苗数7d", "出苗率7d(%)", "出苗数14d", "出苗率14d(%)", "基本苗(万/亩)"],
                    "农艺性状": ["区组", "处理", "越冬前分蘖", "返青后分蘖", "拔节期分蘖", "株高(cm)",
                              "LAI拔节", "LAI抽穗", "干重拔节", "干重抽穗", "干重成熟", "根系干重"],
                    "生理指标": ["区组", "处理", "SPAD拔节", "SPAD抽穗", "SPAD灌浆",
                              "光合速率抽穗", "光合速率灌浆", "活性铁拔节", "活性铁灌浆", "CAT", "POD"],
                    "产量数据": ["区组", "处理", "亩穗数(万穗)", "穗粒数", "千粒重1(g)", "千粒重2(g)",
                              "理论产量(kg/亩)", "实际产量(kg/亩)", "收获指数"],
                    "品质数据": ["区组", "处理", "籽粒蛋白质(%)", "湿面筋(%)", "SDS沉降值(mL)", "籽粒铁(mg/kg)", "面粉铁(mg/kg)"],
                    "操作日志": ["日期", "时间", "操作类型", "区组", "处理", "用量/参数", "天气", "温度℃", "湿度%", "操作人", "备注"],
                }
                for sheet_name, headers in headers_map.items():
                    pd.DataFrame(columns=headers).to_excel(writer, sheet_name=sheet_name, index=False)
            tpl_buf.seek(0)
            st.download_button(
                label="⬇️ 下载空白模板",
                data=tpl_buf,
                file_name="空白记录表模板.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
            )

# ============================================================
# Tab 2: 图表分析
# ============================================================
with tab2:
    st.markdown("### 📊 图表分析")

    yield_df = get_all_records("yield_data")
    if not yield_df.empty and 'actual_yield' in yield_df.columns:
        st.markdown("#### 🌾 各小区实际产量对比")
        chart_data = yield_df[['plot_code', 'actual_yield']].dropna().set_index('plot_code')
        st.bar_chart(chart_data, width='stretch')

        st.markdown("#### 📊 各处理平均产量")
        yield_df['treatment'] = yield_df['plot_code'].str.extract(r'-(.*)')
        treatment_yield = yield_df.groupby('treatment')['actual_yield'].agg(['mean', 'std', 'count']).reset_index()
        treatment_yield.columns = ['处理', '平均产量', '标准差', '样本数']
        st.dataframe(treatment_yield, width='stretch', hide_index=True)
        st.bar_chart(treatment_yield.set_index('处理')['平均产量'], width='stretch')
    else:
        st.info("暂无产量数据可供图表分析。")

    quality_df = get_all_records("quality_data")
    if not quality_df.empty and 'grain_fe' in quality_df.columns:
        st.markdown("#### 🔩 各小区籽粒铁含量对比")
        fe_chart = quality_df[['plot_code', 'grain_fe']].dropna().set_index('plot_code')
        st.bar_chart(fe_chart, width='stretch')
    else:
        st.info("暂无品质数据可供图表分析。")

    physio_df = get_all_records("physiological")
    if not physio_df.empty and 'spad_heading' in physio_df.columns:
        st.markdown("#### 🍃 抽穗期 SPAD 值对比")
        spad_chart = physio_df[['plot_code', 'spad_heading']].dropna().set_index('plot_code')
        st.bar_chart(spad_chart, width='stretch')

    st.markdown("#### 📈 数据录入完成度")
    stats = get_completion_stats()
    pie_data = []
    tbl_cn = {"soil_data":"土壤","phenology":"物候","emergence":"出苗",
              "agronomic_traits":"农艺","physiological":"生理",
              "yield_data":"产量","quality_data":"品质"}
    for k, v in stats.items():
        if k != "operation_log" and isinstance(v, dict):
            pct = v.get("pct", 0)
            if isinstance(pct, (int, float)):
                pie_data.append({"类别": tbl_cn.get(k, k), "完成度(%)": pct})
    if pie_data:
        pie_df = pd.DataFrame(pie_data).set_index("类别")
        st.bar_chart(pie_df, width='stretch')

# ============================================================
# 自动备份
# ============================================================
st.markdown("---")
st.markdown("### 🛡️ 数据备份")
if st.button("💾 立即备份数据库", width='stretch'):
    bak = backup_db()
    st.success(f"✅ 备份已保存为：{bak}")
