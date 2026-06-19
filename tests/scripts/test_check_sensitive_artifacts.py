import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_sensitive_artifacts.py"


def run_scan(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_sensitive_artifact_scan_blocks_financial_file_extensions(tmp_path):
    (tmp_path / "raw").mkdir()
    blocked = tmp_path / "raw" / "transactions.csv"
    blocked.write_text("real-looking,data\n", encoding="utf-8")

    result = run_scan(tmp_path)

    assert result.returncode == 1
    assert "transactions.csv" in result.stdout


def test_sensitive_artifact_scan_allows_marked_synthetic_fixture(tmp_path):
    fixture_dir = tmp_path / "tests" / "fixtures" / "synthetic"
    fixture_dir.mkdir(parents=True)
    fixture = fixture_dir / "alliant_checking.csv"
    fixture.write_text("# SYNTHETIC\nposted_date,description,amount\n", encoding="utf-8")

    result = run_scan(tmp_path)

    assert result.returncode == 0
    assert "No sensitive artifacts found" in result.stdout


def test_sensitive_artifact_scan_ignores_dependency_and_git_folders(tmp_path):
    git_dir = tmp_path / ".git"
    node_modules = tmp_path / "node_modules"
    git_dir.mkdir()
    node_modules.mkdir()
    (git_dir / "ignored.csv").write_text("ignored\n", encoding="utf-8")
    (node_modules / "ignored.sqlite").write_text("ignored\n", encoding="utf-8")

    result = run_scan(tmp_path)

    assert result.returncode == 0
