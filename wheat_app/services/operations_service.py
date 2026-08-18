# -*- coding: utf-8 -*-
"""操作日志业务服务。"""

from wheat_app.repositories.experiment_repository import add_operation, get_operations, get_all_plots


def load_plot_options(base_code=None):
    return get_all_plots(base_code=base_code)["plot_code"].tolist()


def save_operation_record(**kwargs):
    base_code = kwargs.get("base_code")
    if base_code:
        kwargs["base_code"] = base_code
    add_operation(**kwargs)


def load_operation_history(limit=20, base_code=None):
    df = get_operations(limit=limit)
    return df if base_code is None else df[df["base_code"].eq(base_code)] if "base_code" in df.columns else df
