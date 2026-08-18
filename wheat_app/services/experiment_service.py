# -*- coding: utf-8 -*-
"""业务服务层：统一封装与界面无关的核心业务逻辑。"""

from wheat_app.repositories.experiment_repository import (
    get_all_plots,
    get_completion_stats,
    get_operations,
    get_treatment_table_matrix,
)


def get_dashboard_snapshot():
    """返回首页仪表盘所需的聚合信息。"""
    from wheat_app.repositories.experiment_repository import get_all_bases

    stats = get_completion_stats()
    plots_df = get_all_plots()
    bases_df = get_all_bases()
    recent_ops = get_operations(limit=10)
    treatment_matrix = get_treatment_table_matrix()

    return {
        "stats": stats,
        "plots_df": plots_df,
        "recent_ops": recent_ops,
        "treatment_matrix": treatment_matrix,
        "total_plots": int(len(plots_df)) if plots_df is not None else 0,
        "base_count": int(len(bases_df)) if bases_df is not None else 0,
    }


__all__ = ["get_dashboard_snapshot"]
