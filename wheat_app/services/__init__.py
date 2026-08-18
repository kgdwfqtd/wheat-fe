"""Service 层：按业务域对应用逻辑进行统一暴露。"""

from .experiment_service import get_dashboard_snapshot
from .operations_service import load_plot_options as operation_load_plot_options, save_operation_record, load_operation_history
from .phenology_service import (
    load_plot_options as phenology_load_plot_options,
    load_phenology_record,
    save_phenology_record,
    load_emergence_record,
    save_emergence_record,
    load_phenology_table,
    load_emergence_table,
)
from .plot_service import (
    load_plots_data,
    build_plot_display_rows,
    build_qr_zip_for_block,
    build_qr_zip_for_all,
    reset_experiment_data,
    get_layout_summary,
)
from .soil_service import load_soil_records, load_plot_options as soil_load_plot_options, load_soil_record, save_soil_record
from .yield_service import load_yield_records, load_plot_options as yield_load_plot_options, load_yield_record, save_yield_record

__all__ = [
    "get_dashboard_snapshot",
    "load_plots_data",
    "build_plot_display_rows",
    "build_qr_zip_for_block",
    "build_qr_zip_for_all",
    "reset_experiment_data",
    "get_layout_summary",
    "load_soil_records",
    "soil_load_plot_options",
    "load_soil_record",
    "save_soil_record",
    "load_yield_records",
    "yield_load_plot_options",
    "load_yield_record",
    "save_yield_record",
    "operation_load_plot_options",
    "save_operation_record",
    "load_operation_history",
    "phenology_load_plot_options",
    "load_phenology_record",
    "save_phenology_record",
    "load_emergence_record",
    "save_emergence_record",
    "load_phenology_table",
    "load_emergence_table",
]
