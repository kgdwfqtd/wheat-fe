# -*- coding: utf-8 -*-
"""产量数据业务服务。"""

from wheat_app.repositories.experiment_repository import get_all_plots, get_record, get_all_records, upsert_record


def load_yield_records(base_code=None):
    df = get_all_records("yield_data")
    return df if base_code is None else df[df["base_code"].eq(base_code)]


def load_plot_options(base_code=None):
    plots_df = get_all_plots(base_code=base_code)
    return plots_df["plot_code"].tolist()


def load_yield_record(plot_id):
    return get_record("yield_data", plot_id)


def save_yield_record(plot_id, data, base_code=None):
    if not data:
        return False
    payload = dict(data)
    if base_code:
        payload["base_code"] = base_code
    upsert_record("yield_data", plot_id, payload)
    return True
