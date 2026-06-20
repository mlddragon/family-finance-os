from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SOURCE_ROOTS = [
    REPO_ROOT / "apps" / "api",
    REPO_ROOT / "apps" / "web" / "src",
    REPO_ROOT / "scripts",
]
RUNTIME_SOURCE_EXTENSIONS = {".css", ".py", ".ts", ".tsx"}
OBSOLETE_RUNTIME_MARKERS = {"pending_reports_milestone"}


def test_obsolete_planning_markers_do_not_remain_in_runtime_sources():
    offenders: list[str] = []

    for root in RUNTIME_SOURCE_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in RUNTIME_SOURCE_EXTENSIONS:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in OBSOLETE_RUNTIME_MARKERS:
                if marker in text:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} contains {marker}")

    assert offenders == []
