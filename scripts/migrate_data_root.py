#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


LEGACY_PERSONAL = Path.home() / "Dillon_Finances_Data"
LEGACY_QA = Path.home() / "Dillon_Finances_QA_Data"
NEW_PERSONAL = Path.home() / "FamilyFinanceOS_Data"
NEW_QA = Path.home() / "FamilyFinanceOS_QA_Data"

LEGACY_DB = "dillon_finances.sqlite3"
NEW_DB = "family_finance_os.sqlite3"


def _status(path: Path) -> str:
    if path.exists():
        return "present"
    return "missing"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print v0.4.0 data-root migration guidance without moving personal financial data."
    )
    parser.parse_args()

    print("Family Finance OS v0.4.0 rehome migration helper")
    print()
    print("This script does not move data automatically.")
    print("Review paths below, then copy or rename directories manually if needed.")
    print()
    print("Suggested host data roots:")
    print(f"  personal: {NEW_PERSONAL} ({_status(NEW_PERSONAL)})")
    print(f"  qa:       {NEW_QA} ({_status(NEW_QA)})")
    print()
    print("Legacy paths detected:")
    print(f"  personal: {LEGACY_PERSONAL} ({_status(LEGACY_PERSONAL)})")
    print(f"  qa:       {LEGACY_QA} ({_status(LEGACY_QA)})")
    print()
    print("Example manual migration:")
    print(f"  mv {LEGACY_PERSONAL} {NEW_PERSONAL}")
    print(f"  mv {LEGACY_QA} {NEW_QA}")
    print()
    print("SQLite database filename:")
    print(f"  new default: database/{NEW_DB}")
    print(f"  legacy fallback still opens database/{LEGACY_DB} if present")
    print()
    print("Environment variables:")
    print("  prefer FFOS_DATA_ROOT and FFOS_HOST_PORT")
    print("  legacy DILLON_FINANCES_* Compose vars still work for one release")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
