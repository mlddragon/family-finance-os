import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_secret_patterns.py"


def run_scan(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_secret_pattern_scan_blocks_private_key_material(tmp_path):
    candidate = tmp_path / "id_ed25519"
    candidate.write_text("-----BEGIN " + "OPENSSH PRIVATE KEY-----\nabc123\n", encoding="utf-8")

    result = run_scan(tmp_path)

    assert result.returncode == 1
    assert "private key block" in result.stdout
    assert "id_ed25519" in result.stdout


def test_secret_pattern_scan_blocks_common_token_assignment(tmp_path):
    candidate = tmp_path / "settings.env"
    candidate.write_text("API_" + "KEY=livevalue_1234567890abcdef\n", encoding="utf-8")

    result = run_scan(tmp_path)

    assert result.returncode == 1
    assert "secret assignment" in result.stdout


def test_secret_pattern_scan_allows_placeholders(tmp_path):
    candidate = tmp_path / ".env.example"
    candidate.write_text(
        "API_KEY=your-placeholder-api-key\nTOKEN=changeme-placeholder-token\n",
        encoding="utf-8",
    )

    result = run_scan(tmp_path)

    assert result.returncode == 0
    assert "No secret patterns found" in result.stdout


def test_secret_pattern_scan_ignores_dependency_folders(tmp_path):
    ignored = tmp_path / "node_modules" / "package" / "index.js"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("const token = '" + "ghp_" + "abcdefghijklmnopqrstuvwxyz123456';\n", encoding="utf-8")

    result = run_scan(tmp_path)

    assert result.returncode == 0
