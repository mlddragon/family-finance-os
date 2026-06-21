from __future__ import annotations

import json

import pytest

from scripts.qa_reset import QaResetError, reset_qa_data_root
from scripts.qa_seed import seed_baseline_scenario


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
    monkeypatch.setenv("APP_ENV", "qa")
    monkeypatch.setenv("DATASET_KIND", "synthetic")
    monkeypatch.setenv("DEV_MODE", "true")

    manifest_path = seed_baseline_scenario(tmp_path)

    manifest = json.loads(manifest_path.read_text())
    assert manifest["scenario"] == "baseline"
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
