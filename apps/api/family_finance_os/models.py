from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
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
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    validation_summary: Mapped[Optional[str]] = mapped_column(Text)
    source_import_batch_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    report_run_ids_json: Mapped[Optional[str]] = mapped_column(Text)
    settings_snapshot_artifact_id: Mapped[Optional[str]] = mapped_column(String(36))
    decision_export_artifact_id: Mapped[Optional[str]] = mapped_column(String(36))
    artifact_folder_path: Mapped[str] = mapped_column(Text, nullable=False)
    provisional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class PermissionStateEvent(TimestampedModel):
    __tablename__ = "permission_state_events"

    recorded_at: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    effect: Mapped[Optional[str]] = mapped_column(String(20))
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    data_scope_key: Mapped[str] = mapped_column(String(120), nullable=False)
    scope_selector: Mapped[Optional[str]] = mapped_column(String(200))
    reason_note: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_event_id: Mapped[Optional[str]] = mapped_column(String(36))


class ElevatedModeEvent(TimestampedModel):
    __tablename__ = "elevated_mode_events"

    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    context: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose_code: Mapped[str] = mapped_column(String(120), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    exit_reason: Mapped[Optional[str]] = mapped_column(String(120))


class Suggestion(TimestampedModel):
    __tablename__ = "suggestions"

    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(Text)
    proposed_value: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    proposer_actor: Mapped[str] = mapped_column(String(120), nullable=False)
    proposer_actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    suggestion_source: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    decision_event_id: Mapped[Optional[str]] = mapped_column(String(36))
    approval_request_id: Mapped[Optional[str]] = mapped_column(String(36))

    events: Mapped[list["SuggestionEvent"]] = relationship(back_populates="suggestion")


class SuggestionEvent(TimestampedModel):
    __tablename__ = "suggestion_events"

    suggestion_id: Mapped[str] = mapped_column(ForeignKey("suggestions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    suggestion: Mapped[Suggestion] = relationship(back_populates="events")


class ApprovalRequest(TimestampedModel):
    __tablename__ = "approval_requests"

    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(80), nullable=False)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_value: Mapped[Optional[str]] = mapped_column(Text)
    proposed_value: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    proposer_actor: Mapped[str] = mapped_column(String(120), nullable=False)
    proposer_actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    policy_trigger: Mapped[str] = mapped_column(String(120), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(40), nullable=False)
    source_suggestion_id: Mapped[Optional[str]] = mapped_column(ForeignKey("suggestions.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    applied_decision_event_id: Mapped[Optional[str]] = mapped_column(String(36))

    events: Mapped[list["ApprovalRequestEvent"]] = relationship(back_populates="approval_request")


class ApprovalRequestEvent(TimestampedModel):
    __tablename__ = "approval_request_events"

    approval_request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_context_json: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)

    approval_request: Mapped[ApprovalRequest] = relationship(back_populates="events")


class User(TimestampedModel):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username"),
        Index("ix_users_status_role", "status", "role"),
    )

    username: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    passphrase_hash: Mapped[str] = mapped_column(Text, nullable=False)
    passphrase_updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    totp_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recovery_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[str]] = mapped_column(String(40))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[str]] = mapped_column(String(40))
    invited_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    invitation_token_hash: Mapped[Optional[str]] = mapped_column(Text)
    invitation_expires_at: Mapped[Optional[str]] = mapped_column(String(40))


class UserSession(TimestampedModel):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("session_token_hash"),
        Index("ix_user_sessions_user_active", "user_id", "revoked_at", "absolute_expires_at"),
        Index("ix_user_sessions_idle_expiry", "idle_expires_at"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_from: Mapped[str] = mapped_column(String(40), nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String(40), nullable=False)
    idle_expires_at: Mapped[str] = mapped_column(String(40), nullable=False)
    absolute_expires_at: Mapped[str] = mapped_column(String(40), nullable=False)
    revoked_at: Mapped[Optional[str]] = mapped_column(String(40))
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(120))
    user_agent_hash: Mapped[Optional[str]] = mapped_column(String(64))
    client_host: Mapped[Optional[str]] = mapped_column(String(120))


class TotpSecret(TimestampedModel):
    __tablename__ = "totp_secrets"
    __table_args__ = (Index("ix_totp_secrets_user_active", "user_id", "disabled_at"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    secret_version: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_at: Mapped[Optional[str]] = mapped_column(String(40))
    disabled_at: Mapped[Optional[str]] = mapped_column(String(40))
    last_used_counter: Mapped[Optional[int]] = mapped_column(Integer)


class RecoveryCode(TimestampedModel):
    __tablename__ = "recovery_codes"
    __table_args__ = (
        UniqueConstraint("code_hash"),
        Index("ix_recovery_codes_user_status", "user_id", "status"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    code_label: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    used_at: Mapped[Optional[str]] = mapped_column(String(40))
    used_session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("user_sessions.id"))
    rotated_at: Mapped[Optional[str]] = mapped_column(String(40))


class FundPool(TimestampedModel):
    __tablename__ = "fund_pools"
    __table_args__ = (
        UniqueConstraint("pool_key"),
        Index("ix_fund_pools_status_sort", "status", "sort_order"),
    )

    pool_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    rollover_policy: Mapped[str] = mapped_column(String(40), default="none", nullable=False)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class PoolCategoryLink(TimestampedModel):
    __tablename__ = "pool_category_links"
    __table_args__ = (
        UniqueConstraint("fund_pool_id", "category_id", "subcategory_key"),
        Index("ix_pool_category_links_category_active", "category_id", "active"),
        Index("ix_pool_category_links_pool_active", "fund_pool_id", "active"),
    )

    fund_pool_id: Mapped[str] = mapped_column(ForeignKey("fund_pools.id"), nullable=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
    subcategory_key: Mapped[Optional[str]] = mapped_column(String(120))
    link_type: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class MonthlyPoolCommitment(TimestampedModel):
    __tablename__ = "monthly_pool_commitments"
    __table_args__ = (
        UniqueConstraint("fund_pool_id", "month", "status"),
        Index("ix_monthly_pool_commitments_month_status", "month", "status"),
    )

    fund_pool_id: Mapped[str] = mapped_column(ForeignKey("fund_pools.id"), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    committed_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    funding_source: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("decision_events.id"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class FinancialGoal(TimestampedModel):
    __tablename__ = "financial_goals"
    __table_args__ = (
        UniqueConstraint("goal_key"),
        CheckConstraint("length(trim(name)) > 0", name="ck_financial_goals_name_required"),
        Index("ix_financial_goals_status_type", "status", "goal_type"),
        Index("ix_financial_goals_pool_status", "linked_fund_pool_id", "status"),
    )

    goal_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    target_date: Mapped[Optional[str]] = mapped_column(String(10))
    linked_fund_pool_id: Mapped[Optional[str]] = mapped_column(ForeignKey("fund_pools.id"))
    reserved_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    updated_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class BudgetTarget(TimestampedModel):
    __tablename__ = "budget_targets"
    __table_args__ = (
        UniqueConstraint("target_key"),
        Index("ix_budget_targets_month_scope_status", "month", "target_scope", "status"),
        Index("ix_budget_targets_category_month", "category_id", "month"),
        Index("ix_budget_targets_pool_month", "fund_pool_id", "month"),
    )

    target_key: Mapped[str] = mapped_column(String(120), nullable=False)
    month: Mapped[Optional[str]] = mapped_column(String(7))
    target_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(ForeignKey("categories.id"))
    fund_pool_id: Mapped[Optional[str]] = mapped_column(ForeignKey("fund_pools.id"))
    financial_goal_id: Mapped[Optional[str]] = mapped_column(ForeignKey("financial_goals.id"))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    warning_threshold_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    hard_cap_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    review_threshold_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    decision_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("decision_events.id"))


class TransactionAllocation(TimestampedModel):
    __tablename__ = "transaction_allocations"
    __table_args__ = (
        UniqueConstraint("allocation_group_id", "line_number"),
        Index("ix_transaction_allocations_txn_status", "canonical_transaction_id", "status"),
        Index("ix_transaction_allocations_pool_status", "fund_pool_id", "status"),
        Index("ix_transaction_allocations_category_status", "category_id", "status"),
    )

    canonical_transaction_id: Mapped[str] = mapped_column(
        ForeignKey("canonical_transactions.id"),
        nullable=False,
    )
    allocation_group_id: Mapped[str] = mapped_column(String(36), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(120))
    fund_pool_id: Mapped[Optional[str]] = mapped_column(ForeignKey("fund_pools.id"))
    financial_goal_id: Mapped[Optional[str]] = mapped_column(ForeignKey("financial_goals.id"))
    memo: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    decision_event_id: Mapped[Optional[str]] = mapped_column(ForeignKey("decision_events.id"))
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class NetWorthSnapshot(TimestampedModel):
    __tablename__ = "net_worth_snapshots"
    __table_args__ = (
        Index("ix_net_worth_snapshots_date_method", "snapshot_date", "valuation_method"),
        Index("ix_net_worth_snapshots_category_date", "category", "snapshot_date"),
    )

    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False)
    asset_or_liability: Mapped[str] = mapped_column(String(20), nullable=False)
    account_name: Mapped[str] = mapped_column(String(160), nullable=False)
    institution: Mapped[Optional[str]] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(120))
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valuation_method: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False)
    source_notes: Mapped[Optional[str]] = mapped_column(Text)
    include_in_actual_net_worth: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class Receipt(TimestampedModel):
    __tablename__ = "receipts"
    __table_args__ = (
        Index("ix_receipts_transaction_status", "canonical_transaction_id", "status"),
        Index("ix_receipts_purchase_date", "purchase_date"),
        Index("ix_receipts_source_type_status", "source_type", "status"),
    )

    canonical_transaction_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("canonical_transactions.id"),
    )
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    purchase_date: Mapped[str] = mapped_column(String(10), nullable=False)
    receipt_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_file_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_files.id"))
    stored_artifact_path: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    applied_as_split_decision_event_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("decision_events.id"),
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class ReceiptLineItem(TimestampedModel):
    __tablename__ = "receipt_line_items"
    __table_args__ = (
        UniqueConstraint("receipt_id", "line_number"),
        Index("ix_receipt_line_items_receipt", "receipt_id"),
        Index("ix_receipt_line_items_category_review", "category_id", "review_status"),
    )

    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipts.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    item_description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[Optional[str]] = mapped_column(ForeignKey("categories.id"))
    subcategory: Mapped[Optional[str]] = mapped_column(String(120))
    fund_pool_id: Mapped[Optional[str]] = mapped_column(ForeignKey("fund_pools.id"))
    tax_relevant_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reimbursement_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    business_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text)


class ManualObligation(TimestampedModel):
    __tablename__ = "manual_obligations"
    __table_args__ = (
        UniqueConstraint("obligation_key"),
        Index("ix_manual_obligations_month_status", "month", "status"),
        Index("ix_manual_obligations_due_status", "due_date", "status"),
    )

    obligation_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[Optional[str]] = mapped_column(String(10))
    month: Mapped[Optional[str]] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    obligation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    linked_canonical_transaction_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("canonical_transactions.id"),
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class SpendableBalanceSnapshot(TimestampedModel):
    __tablename__ = "spendable_balance_snapshots"
    __table_args__ = (
        Index("ix_spendable_snapshots_month_type", "month", "snapshot_type"),
        Index("ix_spendable_snapshots_close", "monthly_close_id"),
    )

    month: Mapped[str] = mapped_column(String(7), nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(40), nullable=False)
    headline_spendable: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    verified_liquid_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reserved_goal_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    manual_obligations_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    provisional_exposure: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    include_provisional: Mapped[bool] = mapped_column(Boolean, nullable=False)
    card_obligation: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    confidence: Mapped[str] = mapped_column(String(40), nullable=False)
    input_summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    monthly_close_id: Mapped[Optional[str]] = mapped_column(ForeignKey("monthly_closes.id"))
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


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
