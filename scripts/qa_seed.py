from __future__ import annotations

import argparse
from pathlib import Path

from family_finance_os.qa_ops import (
    BASELINE_SCENARIO,
    SCENARIOS,
    QaOpsError,
    QaSeedError,
    seed_baseline_scenario,
    seed_scenario,
)


__all__ = [
    "BASELINE_SCENARIO",
    "SCENARIOS",
    "QaSeedError",
    "seed_baseline_scenario",
    "seed_scenario",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a local QA synthetic scenario.")
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--scenario", default=BASELINE_SCENARIO, choices=sorted(SCENARIOS))
    args = parser.parse_args()

    try:
        manifest_path = seed_scenario(args.data_root, args.scenario)
    except QaOpsError as exc:
        parser.error(str(exc))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
