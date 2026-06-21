from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, event, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


def uuid_text() -> str:
    return str(uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ImportedFactMutationError(RuntimeError):
    """Raised when immutable imported ledger facts are changed after insert."""


class Base(DeclarativeBase):
    pass


class TimestampedModel(Base):
    __abstract__ = True

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_text)
    created_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso, nullable=False)
    updated_at: Mapped[str] = mapped_column(
        String(40),
        default=utc_now_iso,
        onupdate=utc_now_iso,
        nullable=False,
    )


@event.listens_for(TimestampedModel, "init", propagate=True)
def initialize_audit_defaults(target: TimestampedModel, _args, kwargs) -> None:
    if kwargs.get("id") is None:
        kwargs["id"] = uuid_text()
    timestamp = utc_now_iso()
    if kwargs.get("created_at") is None:
        kwargs["created_at"] = timestamp
    if kwargs.get("updated_at") is None:
        kwargs["updated_at"] = timestamp


class Source(TimestampedModel):
    __tablename__ = "sources"

    source_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    accounts: Mapped[list["SourceAccount"]] = relationship(back_populates="source")
    source_files: Mapped[list["SourceFile"]] = relationship(back_populates="source")
    import_batches: Mapped[list["ImportBatch"]] = relationship(back_populates="source")


class SourceAccount(TimestampedModel):
    __tablename__ = "source_accounts"
    __table_args__ = (UniqueConstraint("source_id", "account_key"),)

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    account_key: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    source: Mapped[Source] = relationship(back_populates="accounts")
    source_files: Mapped[list["SourceFile"]] = relationship(back_populates="source_account")
    import_batches: Mapped[list["ImportBatch"]] = relationship(back_populates="source_account")
    imported_rows: Mapped[list["ImportedRow"]] = relationship(back_populates="source_account")
    canonical_transactions: Mapped[list["CanonicalTransaction"]] = relationship(back_populates="source_account")


class SourceFile(TimestampedModel):
    __tablename__ = "source_files"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_accounts.id"))
    import_batch_id: Mapped[Optional[str]] = mapped_column(ForeignKey("import_batches.id"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    storage_status: Mapped[str] = mapped_column(String(40), default="present", nullable=False)
    destroyed_at: Mapped[Optional[str]] = mapped_column(String(40))
    destroyed_by: Mapped[Optional[str]] = mapped_column(String(120))
    destroyed_reason: Mapped[Optional[str]] = mapped_column(Text)
    row_count: Mapped[Optional[int]] = mapped_column(Integer)
    parser_version: Mapped[Optional[str]] = mapped_column(String(80))

    source: Mapped[Source] = relationship(back_populates="source_files")
    source_account: Mapped[Optional[SourceAccount]] = relationship(back_populates="source_files")
    import_batch: Mapped[Optional["ImportBatch"]] = relationship(back_populates="source_files")
    imported_rows: Mapped[list["ImportedRow"]] = relationship(back_populates="source_file")


class ImportBatch(TimestampedModel):
    __tablename__ = "import_batches"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False)
    source_account_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_accounts.id"))
    status: Mapped[str] = mapped_column(String(40), default="detected", nullable=False)
    parser_version: Mapped[Optional[str]] = mapped_column(String(80))
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    row_count: Mapped[Optional[int]] = mapped_column(Integer)
    transaction_date_min: Mapped[Optional[str]] = mapped_column(String(10))
    transaction_date_max: Mapped[Optional[str]] = mapped_column(String(10))
    supersedes_import_batch_id: Mapped[Optional[str]] = mapped_column(ForeignKey("import_batches.id"))

    source: Mapped[Source] = relationship(back_populates="import_batches")
    source_account: Mapped[Optional[SourceAccount]] = relationship(back_populates="import_batches")
    source_files: Mapped[list[SourceFile]] = relationship(back_populates="import_batch")
    imported_rows: Mapped[list["ImportedRow"]] = relationship(back_populates="import_batch")
    events: Mapped[list["ImportBatchEvent"]] = relationship(back_populates="import_batch")


class ImportBatchEvent(TimestampedModel):
    __tablename__ = "import_batch_events"

    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="events")


class CanonicalTransaction(TimestampedModel):
    __tablename__ = "canonical_transactions"

    canonical_identity: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    source_account_id: Mapped[str] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    posted_date: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description_fingerprint: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)

    source_account: Mapped[SourceAccount] = relationship(back_populates="canonical_transactions")
    imported_rows: Mapped[list["ImportedRow"]] = relationship(back_populates="canonical_transaction")


class ImportedRow(TimestampedModel):
    __tablename__ = "imported_rows"

    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    source_file_id: Mapped[str] = mapped_column(ForeignKey("source_files.id"), nullable=False)
    source_account_id: Mapped[str] = mapped_column(ForeignKey("source_accounts.id"), nullable=False)
    canonical_transaction_id: Mapped[Optional[str]] = mapped_column(ForeignKey("canonical_transactions.id"))
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_row_identity: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    posted_date: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_date: Mapped[Optional[str]] = mapped_column(String(10))
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_merchant: Mapped[Optional[str]] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    initial_category: Mapped[Optional[str]] = mapped_column(String(120))
    initial_subcategory: Mapped[Optional[str]] = mapped_column(String(120))
    initial_review_flags_json: Mapped[Optional[str]] = mapped_column(Text)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)

    import_batch: Mapped[ImportBatch] = relationship(back_populates="imported_rows")
    source_file: Mapped[SourceFile] = relationship(back_populates="imported_rows")
    source_account: Mapped[SourceAccount] = relationship(back_populates="imported_rows")
    canonical_transaction: Mapped[Optional[CanonicalTransaction]] = relationship(back_populates="imported_rows")


class ValidationFinding(TimestampedModel):
    __tablename__ = "validation_findings"

    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False)
    resolution_event_id: Mapped[Optional[str]] = mapped_column(String(36))

    events: Mapped[list["ValidationFindingEvent"]] = relationship(back_populates="validation_finding")


class ValidationFindingEvent(TimestampedModel):
    __tablename__ = "validation_finding_events"

    validation_finding_id: Mapped[str] = mapped_column(ForeignKey("validation_findings.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    validation_finding: Mapped[ValidationFinding] = relationship(back_populates="events")


class Setting(TimestampedModel):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("domain", "setting_key"),)

    domain: Mapped[str] = mapped_column(String(120), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(200), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)

    events: Mapped[list["SettingEvent"]] = relationship(back_populates="setting")


class SettingEvent(TimestampedModel):
    __tablename__ = "settings_events"

    setting_id: Mapped[Optional[str]] = mapped_column(ForeignKey("settings.id"))
    domain: Mapped[str] = mapped_column(String(120), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_value_json: Mapped[Optional[str]] = mapped_column(Text)
    new_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    validation_result_json: Mapped[Optional[str]] = mapped_column(Text)
    supersedes_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("settings_events.id"))
    reverts_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("settings_events.id"))

    setting: Mapped[Optional[Setting]] = relationship(back_populates="events")


class DecisionEvent(TimestampedModel):
    __tablename__ = "decision_events"

    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(Text)
    proposed_value: Mapped[Optional[str]] = mapped_column(Text)
    approved_value: Mapped[Optional[str]] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    suggestion_source: Mapped[str] = mapped_column(String(80), default="user", nullable=False)
    supersedes_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("decision_events.id"))
    reverts_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("decision_events.id"))


class Category(TimestampedModel):
    __tablename__ = "categories"

    category_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    created_note: Mapped[Optional[str]] = mapped_column(Text)
    updated_by: Mapped[Optional[str]] = mapped_column(String(120))
    updated_note: Mapped[Optional[str]] = mapped_column(Text)


class Job(TimestampedModel):
    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[str] = mapped_column(String(40), default=utc_now_iso, nullable=False)
    finished_at: Mapped[Optional[str]] = mapped_column(String(40))
    input_json: Mapped[Optional[str]] = mapped_column(Text)
    output_json: Mapped[Optional[str]] = mapped_column(Text)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    logs_path: Mapped[Optional[str]] = mapped_column(Text)
    root_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jobs.id"))

    report_runs: Mapped[list["ReportRun"]] = relationship(back_populates="job")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="producing_job")


class ReportRun(TimestampedModel):
    __tablename__ = "report_runs"

    report_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jobs.id"))
    validation_status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    input_snapshot_json: Mapped[Optional[str]] = mapped_column(Text)
    output_summary_json: Mapped[Optional[str]] = mapped_column(Text)

    job: Mapped[Optional[Job]] = relationship(back_populates="report_runs")


class Artifact(TimestampedModel):
    __tablename__ = "artifacts"

    artifact_type: Mapped[str] = mapped_column(String(120), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    producing_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("jobs.id"))
    source_inputs_json: Mapped[Optional[str]] = mapped_column(Text)
    retention_category: Mapped[Optional[str]] = mapped_column(String(80))
    sensitivity: Mapped[str] = mapped_column(String(80), nullable=False)

    producing_job: Mapped[Optional[Job]] = relationship(back_populates="artifacts")


class MonthlyClose(TimestampedModel):
    __tablename__ = "monthly_closes"
    __table_args__ = (UniqueConstraint("month", "status"),)

    month: Mapped[str] = mapped_column(String(7), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    validation_summary: Mapped[Optional[str]] = mapped_column(Text)
    source_import_batch_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    report_run_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    settings_snapshot_artifact_id: Mapped[Optional[str]] = mapped_column(String(36))
    decision_export_artifact_id: Mapped[Optional[str]] = mapped_column(String(36))
    artifact_folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    provisional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


@event.listens_for(Session, "before_flush")
def prevent_imported_row_mutation(session: Session, _flush_context, _instances) -> None:
    for obj in session.dirty:
        if isinstance(obj, ImportedRow) and inspect(obj).persistent:
            if session.is_modified(obj, include_collections=False):
                raise ImportedFactMutationError(
                    "Imported rows are immutable after accepted insert."
                )

    for obj in session.deleted:
        if isinstance(obj, ImportedRow) and inspect(obj).persistent:
            raise ImportedFactMutationError(
                "Imported rows are immutable after accepted insert."
            )
