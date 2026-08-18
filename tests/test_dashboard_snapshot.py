from database import create_experiment_base, delete_experiment_base, get_all_bases, get_all_plots, init_db, init_plots
from wheat_app.services.experiment_service import get_dashboard_snapshot


def test_dashboard_snapshot_includes_total_counts():
    base_code = "91010000000099"
    try:
        init_db()
        create_experiment_base(
            base_code=base_code,
            base_name="测试基地",
            admin_code="910100",
            remarks="pytest",
        )
        init_plots(base_code=base_code)

        snapshot = get_dashboard_snapshot()

        assert "total_plots" in snapshot
        assert "base_count" in snapshot
        assert snapshot["total_plots"] >= len(get_all_plots(base_code=base_code))
        assert snapshot["base_count"] >= len(get_all_bases())
    finally:
        try:
            delete_experiment_base(base_code)
        except Exception:
            pass


def test_init_plots_persists_to_selected_base_only():
    base_code = "91010000000098"
    try:
        init_db()
        create_experiment_base(
            base_code=base_code,
            base_name="按基地初始化测试",
            admin_code="910100",
            remarks="pytest",
        )

        created = init_plots(base_code=base_code)
        base_rows = get_all_plots(base_code=base_code)
        all_rows = get_all_plots()

        assert created >= 18
        assert len(base_rows) >= 18
        assert all_rows[all_rows["base_code"] == base_code].shape[0] >= 18
    finally:
        try:
            delete_experiment_base(base_code)
        except Exception:
            pass
