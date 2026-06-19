from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import sessionmaker

from dillon_finances.database import create_sqlite_engine, upgrade_database
from dillon_finances.jobs import record_job
from dillon_finances.models import (
    Artifact,
    CanonicalTransaction,
    DecisionEvent,
    ImportedFactMutationError,
    ImportedRow,
    ImportBatch,
    Job,
    MonthlyClose,
    ReportRun,
    Setting,
    SettingEvent,
    Source,
    SourceAccount,
    SourceFile,
    ValidationFinding,
)


EXPECTED_TABLES = {
    "sources",
    "source_accounts",
    "source_files",
    "import_batches",
    "imported_rows",
    "canonical_transactions",
    "validation_findings",
    "settings",
    "settings_events",
    "decision_events",
    "jobs",
    "report_runs",
    "artifacts",
    "monthly_closes",
}


def test_migration_upgrade_creates_all_v1_tables(tmp_path):
    database_path = tmp_path / "database" / "dillon_finances.sqlite3"

    upgrade_database(database_path)
    engine = create_sqlite_engine(database_path)

    assert EXPECTED_TABLES.issubset(set(inspect(engine).get_table_names()))


def test_models_insert_and_query_v1_audit_records(tmp_path):
    database_path = tmp_path / "database" / "dillon_finances.sqlite3"
    upgrade_database(database_path)
    engine = create_sqlite_engine(database_path)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        source = Source(
            source_key="chase_prime_visa",
            display_name="Chase Prime Visa",
            source_type="credit_card",
        )
        account = SourceAccount(
            source=source,
            account_key="chase_prime_visa_primary",
            display_name="Chase Prime Visa Primary",
            account_type="credit_card",
        )
        batch = ImportBatch(
            source=source,
            source_account=account,
            status="accepted",
            parser_version="synthetic-v1",
            row_count=1,
            validation_status="passed",
        )
        source_file = SourceFile(
            source=source,
            source_account=account,
            import_batch=batch,
            original_filename="SYNTHETIC_chase_prime_visa.csv",
            stored_path="/data/raw/chase/2026/batch/SYNTHETIC_chase_prime_visa.csv",
            file_sha256="a" * 64,
            byte_size=128,
            validation_status="passed",
            row_count=1,
            parser_version="synthetic-v1",
        )
        canonical = CanonicalTransaction(
            canonical_identity="canonical-identity-1",
            source_account=account,
            posted_date="2026-01-02",
            amount=Decimal("-12.34"),
            description_fingerprint="synthetic-merchant",
            status="active",
        )
        imported_row = ImportedRow(
            import_batch=batch,
            source_file=source_file,
            source_account=account,
            canonical_transaction=canonical,
            source_row_number=2,
            imported_row_hash="b" * 64,
            imported_row_identity="imported-row-identity-1",
            posted_date="2026-01-02",
            raw_description="SYNTHETIC MERCHANT",
            amount=Decimal("-12.34"),
            direction="debit",
            parser_version="synthetic-v1",
        )
        finding = ValidationFinding(
            severity="info",
            code="synthetic_check",
            message="Synthetic validation finding",
            target_type="import_batch",
            target_id=batch.id,
            status="open",
        )
        setting = Setting(
            domain="freshness",
            setting_key="chase_prime_visa.max_age_days",
            value_json='{"days": 14}',
        )
        setting_event = SettingEvent(
            setting=setting,
            domain="freshness",
            setting_key="chase_prime_visa.max_age_days",
            previous_value_json=None,
            new_value_json='{"days": 14}',
            actor="mason",
            notes="Initial synthetic setting",
        )
        decision_event = DecisionEvent(
            target_type="canonical_transaction",
            target_id=canonical.id,
            decision_type="category_change",
            field_name="category",
            previous_value=None,
            proposed_value="Household",
            approved_value="Household",
            actor="mason",
            suggestion_source="user",
        )
        job = record_job(
            session,
            job_type="import",
            status="completed",
            actor="mason",
            input_json='{"source": "synthetic"}',
        )
        report = ReportRun(
            report_type="import_validation_summary",
            status="completed",
            job=job,
            validation_status="passed",
        )
        artifact = Artifact(
            artifact_type="report",
            path="/data/reports/synthetic/import_validation_summary.md",
            sha256="c" * 64,
            byte_size=256,
            title="Synthetic Import Validation Summary",
            producing_job=job,
            sensitivity="synthetic",
        )
        close = MonthlyClose(
            month="2026-01",
            status="draft",
            actor="mason",
            validation_summary="Synthetic validation passed",
            report_run_ids_json=f'["{report.id}"]',
            settings_snapshot_artifact_id=artifact.id,
            artifact_folder_path="/data/monthly_close/2026-01",
            provisional=True,
        )

        session.add_all(
            [
                source,
                account,
                batch,
                source_file,
                canonical,
                imported_row,
                finding,
                setting,
                setting_event,
                decision_event,
                report,
                artifact,
                close,
            ]
        )
        session.commit()

        ids = [
            source.id,
            account.id,
            batch.id,
            source_file.id,
            canonical.id,
            imported_row.id,
            finding.id,
            setting.id,
            setting_event.id,
            decision_event.id,
            job.id,
            report.id,
            artifact.id,
            close.id,
        ]
        assert all(UUID(value) for value in ids)
        assert all(record.created_at.endswith("+00:00") for record in [source, batch, job])
        assert session.scalar(select(Source).where(Source.source_key == "chase_prime_visa")) == source
        assert session.scalar(select(Job).where(Job.job_type == "import")) == job
        assert session.scalar(select(MonthlyClose).where(MonthlyClose.month == "2026-01")) == close


def test_imported_rows_are_immutable_after_insert(tmp_path):
    database_path = tmp_path / "database" / "dillon_finances.sqlite3"
    upgrade_database(database_path)
    engine = create_sqlite_engine(database_path)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        source = Source(
            source_key="alliant_checking",
            display_name="Alliant Checking",
            source_type="checking",
        )
        account = SourceAccount(
            source=source,
            account_key="alliant_checking_primary",
            display_name="Alliant Checking Primary",
            account_type="checking",
        )
        batch = ImportBatch(source=source, source_account=account, status="accepted")
        source_file = SourceFile(
            source=source,
            source_account=account,
            import_batch=batch,
            original_filename="SYNTHETIC_alliant_checking.csv",
            stored_path="/data/raw/alliant/2026/batch/SYNTHETIC_alliant_checking.csv",
            file_sha256="d" * 64,
            byte_size=128,
            validation_status="passed",
            row_count=1,
            parser_version="synthetic-v1",
        )
        imported_row = ImportedRow(
            import_batch=batch,
            source_file=source_file,
            source_account=account,
            source_row_number=2,
            imported_row_hash="e" * 64,
            imported_row_identity="imported-row-identity-2",
            posted_date="2026-01-03",
            raw_description="SYNTHETIC PAYCHECK",
            amount=Decimal("1000.00"),
            direction="credit",
            parser_version="synthetic-v1",
        )
        session.add_all([source, account, batch, source_file, imported_row])
        session.commit()

        imported_row.raw_description = "MUTATED DESCRIPTION"

        with pytest.raises(ImportedFactMutationError, match="Imported rows are immutable"):
            session.commit()
