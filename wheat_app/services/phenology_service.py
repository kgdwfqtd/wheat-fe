# -*- coding: utf-8 -*-
"""物候与出苗业务服务。"""

from wheat_app.repositories.experiment_repository import (
    get_all_plots,
    get_record,
    get_all_records,
    upsert_record,
)


def load_plot_options(base_code=None):
    plots_df = get_all_plots(base_code=base_code)
    return plots_df["plot_code"].tolist()


def load_phenology_record(plot_id):
    return get_record("phenology", plot_id)


def save_phenology_record(plot_id, data, base_code=None):
    if not data:
        return False
    payload = dict(data)
    if base_code:
        payload["base_code"] = base_code
    upsert_record("phenology", plot_id, payload)
    return True


def load_emergence_record(plot_id):
    return get_record("emergence", plot_id)


def save_emergence_record(plot_id, data, base_code=None):
    if not data:
        return False
    payload = dict(data)
    if base_code:
        payload["base_code"] = base_code
    upsert_record("emergence", plot_id, payload)
    return True


def load_phenology_table(base_code=None):
    df = get_all_records("phenology")
    return df if base_code is None else df[df["base_code"].eq(base_code)]


def load_emergence_table(base_code=None):
    df = get_all_records("emergence")
    return df if base_code is None else df[df["base_code"].eq(base_code)]


__all__ = [
    "load_plot_options",
    "load_phenology_record",
    "save_phenology_record",
    "load_emergence_record",
    "save_emergence_record",
    "load_phenology_table",
    "load_emergence_table",
]
