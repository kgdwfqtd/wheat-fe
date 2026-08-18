# -*- coding: utf-8 -*-
"""土壤数据业务服务。"""

from wheat_app.repositories.experiment_repository import get_all_plots, get_record, get_all_records, upsert_record


def load_soil_records(base_code=None):
    if base_code:
        return get_all_records("soil_data").query(f"base_code == '{base_code}'")
    return get_all_records("soil_data")


def load_plot_options(base_code=None):
    plots_df = get_all_plots(base_code=base_code)
    return plots_df["plot_code"].tolist()


def load_soil_record(plot_id, phase):
    return get_record("soil_data", plot_id, extra_keys={"phase": phase})


def save_soil_record(plot_id, phase, data, base_code=None):
    if not data:
        return False
    payload = dict(data)
    if base_code:
        payload["base_code"] = base_code
    upsert_record("soil_data", plot_id, payload, extra_keys={"phase": phase})
    return True
