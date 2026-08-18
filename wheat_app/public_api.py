# -*- coding: utf-8 -*-
"""统一的应用公开入口。用于集中暴露当前推荐的项目访问方式。"""

from wheat_app.config import *  # noqa: F401,F403
from wheat_app.repositories import *  # noqa: F401,F403
from wheat_app.services import *  # noqa: F401,F403

__all__ = [
    "BASE_DIR",
    "DB_CONFIG",
    "DB_URL",
    "DB_BACKUP_MAX",
    "PLOT_AREA_M2",
    "PLOT_RATIO",
    "NF_SPLIT",
    "NF_SPRAY_WATER_L_PER_MU",
    "TKW_DIFF_WARN_PCT",
    "EMERGENCE_RATE_WARN",
    "PAGE_TITLE",
    "PAGE_ICON",
    "PROJECT_ROOT",
    "init_db",
    "init_plots",
    "get_all_plots",
    "get_plot_by_code",
    "get_completion_stats",
    "get_treatment_table_matrix",
    "get_all_records",
    "get_record",
    "upsert_record",
    "add_operation",
    "get_operations",
    "export_to_excel",
    "backup_db",
    "reset_all_data",
    "create_experiment_base",
    "get_all_bases",
    "get_base_by_code",
    "update_experiment_base",
    "delete_experiment_base",
    "get_dashboard_snapshot",
]
