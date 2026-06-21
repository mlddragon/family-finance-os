from __future__ import annotations

import json

import pytest

from scripts.qa_reset import QaResetError, reset_qa_data_root
from scripts.qa_seed import SCENARIOS, QaSeedError, seed_baseline_scenario, seed_scenario


def enable_qa_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "qa")
    monkeypatch.setenv("DATASET_KIND", "synthetic")
    monkeypatch.setenv("DEV_MODE", "true")


def test_qa_reset_refuses_without_exact_confirmation(tmp_path):
    data_root = tmp_path / "Dillon_Finances_QA_Data"
    data_root.mkdir()

    with pytest.raises(QaResetError, match="confirmation"):
        reset_qa_data_root(
            data_root=data_root,
            app_env="qa",
            dataset_kind="synthetic",
            confirmation="wrong",
        )

    assert data_root.exists()


def test_qa_reset_refuses_personal_environment_identity(tmp_path):
    data_root = tmp_path / "Dillon_Finances_QA_Data"
    data_root.mkdir()

    with pytest.raises(QaResetError, match="QA/synthetic"):
        reset_qa_data_root(
            data_root=data_root,
            app_env="personal",
            dataset_kind="personal",
            confirmation="RESET QA DATA",
        )

    assert data_root.exists()


def test_qa_reset_recreates_required_data_root_dirs(tmp_path):
    data_root = tmp_path / "Dillon_Finances_QA_Data"
    (data_root / "database").mkdir(parents=True)
    (data_root / "database" / "old.sqlite3").write_text("synthetic old db")

    reset_qa_data_root(
        data_root=data_root,
        app_env="qa",
        dataset_kind="synthetic",
        confirmation="RESET QA DATA",
    )

    assert not (data_root / "database" / "old.sqlite3").exists()
    assert (data_root / "inbox").is_dir()
    assert (data_root / "manifests").is_dir()


def test_baseline_seed_writes_manifest_and_closed_loop_outputs(tmp_path, monkeypatch):
    enable_qa_seed(monkeypatch)

    manifest_path = seed_baseline_scenario(tmp_path)

    manifest = json.loads(manifest_path.read_text())
    assert manifest["scenario"] == "baseline"
    assert manifest["scenario_version"] == "0.4.0"
    assert manifest["dataset_kind"] == "synthetic"
    assert sorted(manifest["accepted_source_keys"]) == [
        "alliant_checking",
        "alliant_credit_card",
        "alliant_savings",
        "chase_prime_visa",
    ]
    assert manifest["artifact_counts"]["reports"] > 0
    assert manifest["artifact_counts"]["monthly_close"] > 0
    assert manifest["artifact_counts"]["advisor_export"] > 0
    assert manifest["operator_summary"]["runtime"]["qa_controls_enabled"] is True
    assert manifest["synthetic_artifact_marker"] == "QA synthetic demo - not real financial data"


def test_qa_seed_rejects_non_qa_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "personal")
    monkeypatch.setenv("DATASET_KIND", "personal")
    monkeypatch.setenv("DEV_MODE", "false")

    with pytest.raises(QaSeedError, match="APP_ENV=qa"):
        seed_scenario(tmp_path, "baseline")


def test_qa_seed_rejects_unknown_scenario(tmp_path, monkeypatch):
    enable_qa_seed(monkeypatch)

    with pytest.raises(QaSeedError, match="Unknown QA scenario"):
        seed_scenario(tmp_path, "not-a-scenario")


def test_named_qa_scenarios_are_registered():
    assert sorted(SCENARIOS) == [
        "baseline",
        "blocked-import",
        "monthly-close-ready",
        "review-backlog",
        "stale-source",
    ]


def test_stale_source_seed_writes_expected_manifest_state(tmp_path, monkeypatch):
    enable_qa_seed(monkeypatch)

    manifest_path = seed_scenario(tmp_path, "stale-source")

    manifest = json.loads(manifest_path.read_text())
    assert manifest["scenario"] == "stale-source"
    assert manifest["blocked_finalize_status_code"] == 409
    assert manifest["expected_operator_state"]["stale_required_sources"] == ["chase_prime_visa"]
    assert "source_stale" in manifest["validation_findings"]["codes"]
    assert manifest["operator_summary"]["monthly_close"]["ready_for_final"] is False
    assert "stale_required_sources" in manifest["operator_summary"]["monthly_close"]["blockers"]
    assert manifest["transactions"]["unreviewed"] == 0


def test_blocked_import_seed_writes_expected_manifest_and_quarantine(tmp_path, monkeypatch):
    enable_qa_seed(monkeypatch)

    manifest_path = seed_scenario(tmp_path, "blocked-import")

    manifest = json.loads(manifest_path.read_text())
    assert manifest["scenario"] == "blocked-import"
    assert manifest["blocked_accept_status_code"] == 409
    assert manifest["blocked_validation_codes"] == ["schema_mismatch"]
    assert manifest["validation_findings"]["open_blocking"] == 1
    assert "schema_mismatch" in manifest["validation_findings"]["codes"]
    assert manifest["operator_summary"]["next_action"]["code"] == "resolve_validation_blockers"
    assert list((tmp_path / "quarantine").glob("**/SYNTHETIC_unknown_source_blocked-import.csv"))


def test_review_backlog_seed_writes_unreviewed_transactions(tmp_path, monkeypatch):
    enable_qa_seed(monkeypatch)

    manifest_path = seed_scenario(tmp_path, "review-backlog")

    manifest = json.loads(manifest_path.read_text())
    assert manifest["scenario"] == "review-backlog"
    assert manifest["transactions"]["total"] > 0
    assert manifest["transactions"]["unreviewed"] == manifest["transactions"]["total"]
    assert manifest["operator_summary"]["next_action"]["code"] == "review_ledger_decisions"
    assert manifest["validation_findings"]["open_blocking"] == 0


def test_monthly_close_ready_seed_writes_final_close_and_export_state(tmp_path, monkeypatch):
    enable_qa_seed(monkeypatch)

    manifest_path = seed_scenario(tmp_path, "monthly-close-ready")

    manifest = json.loads(manifest_path.read_text())
    assert manifest["scenario"] == "monthly-close-ready"
    assert manifest["monthly_close_status"] == "final"
    assert manifest["operator_summary"]["monthly_close"]["status"] == "final"
    assert manifest["operator_summary"]["next_action"]["code"] == "refresh_source_data"
    assert manifest["transactions"]["unreviewed"] == 0
    assert manifest["artifact_counts"]["reports"] > 0
    assert manifest["artifact_counts"]["monthly_close_final"] > 0
    assert manifest["artifact_counts"]["advisor_export"] > 0
