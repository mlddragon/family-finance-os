# Import Validation Contract v1

This document defines the proposed v1 import validation contract for the first Dillon Finances closed-loop ledger sources: Alliant Checking, Alliant Savings, Alliant Credit Card, and Chase Prime Visa. It is a planning artifact only. It does not create parser code, create a database schema, add dependencies, migrate data, or commit any financial exports.

## Status

- Proposed for owner review.
- App implementation has not started.
- No source files or transaction data have been migrated.
- Exact parser code and database schema remain deferred to implementation planning.
- Source header examples must be confirmed with synthetic or header-only samples before implementation.

## Contract Goal

The v1 import process must accept manually downloaded ledger exports only when the app can prove what was received, which source/account it belongs to, whether it is safe to normalize, and what review work remains.

The contract must prevent:

- Raw file mutation.
- Silent duplicate spending.
- Silent source/account misidentification.
- Hidden parser failures.
- Reports that look final when source data is stale, missing, blocked, or unreviewed.

## Recommendation

Strong recommendation: use a conservative, validation-first import contract with batch acceptance, explicit warnings, quarantine for blocking failures, and no silent deduplication. This is the best fit for a family financial operating system because source exports are manual, source formats may change without notice, and the cost of double-counting or misclassifying ledger transactions is higher than the cost of asking for owner review. The contract should prefer visible provisional states over false confidence.

Serious alternatives considered:

- File-by-file acceptance only: simpler to implement, but weaker for monthly refresh workflows where several required sources must be evaluated together.
- Lenient import with post-hoc cleanup: faster to get rows into the system, but it risks normalizing bad data before source/account identity, duplicates, and amount signs are proven.
- Silent dedupe on import: convenient for overlapping exports, but unsafe because it can hide evidence and make duplicate logic hard to audit.

## Source Scope

v1 required ledger sources:

- Alliant Checking.
- Alliant Savings.
- Alliant Credit Card.
- Chase Prime Visa.

v1 excluded sources:

- Amazon, Walmart, Costco, Target, Temu, PayPal, Venmo, Greenlight, mortgage PDFs, and other detail sources.
- Automated bank connections.
- Stored credentials.
- Stored browser sessions.
- PDF statement parsing.

## Approved Import Mode

Approved direction: guided manual import.

Accepted input paths:

- Files placed in `DATA_ROOT/inbox/`.
- Files uploaded through the future local browser UI.

Rules:

- Raw exports stay outside git.
- Raw exports are never edited.
- Every imported file gets a source file record with path, original filename, hash, byte size, source guess, validation status, and parser/version reference.
- Accepted files are preserved under `DATA_ROOT/raw/{source}/{YYYY}/{import_batch_id}/`.
- Files that fail or need owner attention are moved or copied to `DATA_ROOT/quarantine/` with a validation reason and recovery action.

## Import Unit

Approved direction: import batches are the acceptance unit; files can still be validated individually.

An import batch should represent one coherent refresh cycle. A batch may contain:

- One source file.
- Multiple files for the same source if the institution export splits data.
- Multiple source files imported together for a monthly refresh.

Rules:

- Validation can run per file before batch acceptance.
- Batch acceptance requires all blocking file-level and batch-level issues resolved.
- Warnings can be accepted only when explicitly acknowledged.
- Batch records must capture included source files, source scope, row counts, transaction date min/max, validation status, parser/version, and supersedes/superseded-by links where applicable.

## Source Profiles

Source profiles define how the app recognizes a file and what parser contract applies. Exact source-header profiles must be confirmed with synthetic or header-only samples before implementation.

### Alliant Checking

Purpose:

- Required core cashflow source.

Expected account type:

- Depository checking.

Known contract from prior work:

- Prior normalized Alliant data used the common normalized ledger concepts: posted date, raw description, amount, account/source metadata, review flags, and duplicate review.
- Prior review logic required at least `posted_date`, `description_raw`, and `amount` after normalization.

Implementation-planning requirement:

- Confirm the raw Alliant checking export columns before parser implementation.
- Capture a header-only or synthetic sample in docs/tests, not real financial data.

### Alliant Savings

Purpose:

- Required core cash/balance movement source.

Expected account type:

- Depository savings.

Known contract from prior work:

- Same normalized ledger requirements as Alliant Checking.
- Savings transactions may contain transfers that should be flagged rather than silently classified.

Implementation-planning requirement:

- Confirm whether Alliant checking and savings share one raw export format or require separate profiles.

### Alliant Credit Card

Purpose:

- Required card spending source.

Expected account type:

- Credit card.

Known contract from prior work:

- Same normalized ledger requirements as other Alliant sources after parsing.
- Card transactions can contain refunds, payments, interest, and split-prone merchants that require review.

Implementation-planning requirement:

- Confirm raw Alliant credit-card export columns and amount-sign conventions before parser implementation.

### Chase Prime Visa

Purpose:

- Required card spending source.

Expected account type:

- Credit card.

Known candidate raw export columns from prior prototype:

- `Transaction Date`
- `Post Date`
- `Description`
- `Category`
- `Type`
- `Amount`

Known candidate normalized mapping from prior prototype:

- `Post Date` maps to posted date.
- `Transaction Date` maps to authorized/effective date.
- `Description` maps to raw description.
- `Amount` maps to signed amount.
- `Category` and `Type` can seed notes, initial category suggestions, and review reasons.

Implementation-planning requirement:

- Confirm the current Chase Prime Visa export still uses this raw column profile before parser implementation.
- Confirm amount-sign convention for purchases, payments, refunds, fees, and interest.

## Normalized Ledger Target Contract

The parser implementation should normalize accepted rows toward the later database model, not toward a permanent CSV design.

Required normalized concepts:

- Source account id.
- Source name.
- Account nickname.
- Account type.
- Account last4 or stable local account key.
- Source file id.
- Source row number.
- Import batch id.
- Posted date.
- Authorized/effective date when available.
- Raw description.
- Normalized merchant where available.
- Amount.
- Direction.
- Balance if available.
- Source-provided transaction id if available.
- Imported row identity.
- Canonical transaction identity.
- Initial category suggestion.
- Initial subcategory suggestion.
- Initial review flags and reasons.
- Parser/version.
- Created timestamp.

Rules:

- Normalized rows are immutable imported facts after accepted import.
- Human review does not overwrite normalized imported facts.
- Corrections require a new import batch/version or an append-only decision event, depending on the correction type.
- CSV/JSON exports remain audit/export formats, not the active storage layer.

## Validation Severity Model

Every validation finding should have:

- Severity: info, warning, or blocking.
- Stable validation code.
- Target type: file, batch, imported row, canonical transaction, source, account, report, or monthly close.
- Target id when available.
- Human-readable message.
- Detected timestamp.
- Status: open, acknowledged, resolved, or ignored.
- Resolution event/link where applicable.

Severity meanings:

- Info: visible context that does not require action.
- Warning: import can proceed only with visible acknowledgment; downstream reports may be provisional.
- Blocking: import acceptance, report readiness, or monthly close readiness is stopped until resolved.

## File-Level Validations

### Existence And Accessibility

Codes:

- `file_missing`
- `file_unreadable`
- `file_empty`

Severity:

- Blocking.

Rules:

- A required source with no file for the target refresh remains missing/stale.
- Empty files are quarantined.
- Unreadable files remain in inbox or quarantine with a clear next action.

### File Type And Encoding

Codes:

- `unsupported_file_type`
- `unsupported_encoding`
- `csv_parse_failed`

Severity:

- Blocking.

Rules:

- v1 accepts CSV-like transaction exports only.
- XLS/XLSX, PDF, browser session artifacts, and credential/session files are rejected for v1 ledger import.
- Parser failures must not produce partial accepted imports.

### Source Detection

Codes:

- `source_unknown`
- `source_conflict`
- `account_unknown`
- `account_conflict`

Severity:

- Blocking when the app cannot confidently identify the source/account.
- Warning when source is known but account metadata needs owner confirmation.

Rules:

- Source detection can use filename hints, header profile, known account metadata, and row-pattern checks.
- Source/account identity cannot be inferred from filename alone.
- If a file could belong to more than one source/account, it must go to validation review.

### Header/Profile Validation

Codes:

- `schema_missing_required_column`
- `schema_unexpected_required_profile`
- `schema_duplicate_column`
- `schema_empty_header`
- `schema_new_optional_column`

Severity:

- Missing required columns: blocking.
- Duplicate columns: blocking.
- Empty header: blocking.
- New optional columns: warning.

Rules:

- Header names should be matched case-insensitively after trimming whitespace.
- The raw header list should be recorded in source file metadata.
- New optional columns should be surfaced so parser profiles can evolve deliberately.

## Row-Level Validations

### Row Count

Codes:

- `row_count_zero`
- `row_count_unusually_low`
- `row_count_unusually_high`
- `row_count_changed_from_prior_export`

Severity:

- Zero rows: blocking.
- Unusual counts: warning unless paired with other blocking symptoms.

Rules:

- v1 should compare row counts to the source's recent import history when available.
- The first import for a source can warn but should not block solely because no baseline exists.

### Date Parsing

Codes:

- `date_parse_failed`
- `posted_date_missing`
- `authorized_date_parse_failed`
- `future_posted_date`
- `date_range_unexpected`

Severity:

- Missing or unparsable posted date: blocking.
- Authorized/effective date issues: warning if posted date is valid.
- Future posted dates: blocking unless owner explicitly resolves.
- Unexpected date range: warning or blocking depending on source/batch context.

Rules:

- Posted date is required for every accepted row.
- Authorized/effective date is optional when a source does not provide it.
- The batch records min/max posted date.

### Amount Parsing And Direction

Codes:

- `amount_parse_failed`
- `amount_missing`
- `amount_zero`
- `amount_sign_unexpected`
- `amount_precision_invalid`

Severity:

- Missing or unparsable amount: blocking.
- Zero amount: warning unless source-specific rules justify it.
- Unexpected sign: warning or blocking depending on source/account type and transaction type.
- Invalid precision beyond cents: blocking for v1 ledger sources.

Rules:

- Amounts must normalize to signed decimal values with cent precision.
- Direction is derived from normalized amount after source-specific sign rules.
- Sign conventions must be source-profile-specific and tested with synthetic rows.
- Credit card purchases, payments, refunds, fees, and interest must be explicitly covered by source tests before implementation.

### Description And Merchant

Codes:

- `description_missing`
- `description_unusually_short`
- `merchant_normalization_empty`
- `merchant_review_required`

Severity:

- Missing raw description: warning by default, blocking if it prevents identity/collision checks.
- Merchant normalization empty: info or warning, never a blocker by itself.

Rules:

- Raw description should be preserved exactly after safe text trimming.
- Merchant normalization can seed review, but it is not owner-approved truth.

### Row Identity

Codes:

- `imported_row_identity_collision`
- `canonical_identity_collision`
- `canonical_duplicate_candidate`
- `source_transaction_id_duplicate`

Severity:

- Imported row identity collision within the same file/batch: blocking.
- Canonical identity collision with identical evidence: info or warning.
- Ambiguous canonical duplicate candidate: blocking until reviewed or resolved.
- Source-provided transaction id duplicate: warning or blocking depending on row equality.

Rules:

- Imported row identity proves the exact evidence row.
- Canonical transaction identity prevents duplicate spending across overlapping exports.
- Duplicate/overlap detection must link imported rows to the same canonical transaction only when deterministic and unambiguous.
- Ambiguous matches go to validation review, not silent merge.
- Prior prototype deduplication by dropping rows must not be inherited as v1 behavior.

## Batch-Level Validations

### Required Source Coverage

Codes:

- `required_source_missing`
- `source_stale`
- `source_refresh_incomplete`

Severity:

- Missing required source for monthly close: blocking for close readiness.
- Stale source: warning for import acceptance, provisional for reports, blocking for final monthly close when the source is required for the close period.

Rules:

- Initial default stale threshold is 14 days for checking and card sources.
- Latest successful import date and latest transaction date must be tracked per source.
- Reports are marked provisional if any required source is stale or missing.

### Overlapping Exports

Codes:

- `export_overlap_detected`
- `overlap_duplicate_resolved`
- `overlap_duplicate_ambiguous`

Severity:

- Resolved overlap: info or warning.
- Ambiguous overlap: blocking.

Rules:

- Overlapping exports are expected and should be supported.
- The app should preserve all imported row evidence.
- Reports should count canonical transactions, not every imported row.

### Import Batch Mismatch

Codes:

- `batch_source_mismatch`
- `batch_period_gap`
- `batch_period_overlap`
- `batch_validation_incomplete`

Severity:

- Source mismatch: blocking.
- Period gap/overlap: warning unless it threatens duplicate spending or close readiness.
- Incomplete validation: blocking.

Rules:

- A batch cannot be accepted until all included files have validation results.
- A batch should expose the source coverage it does and does not provide.

## Source-Specific Validation Defaults

### Alliant Checking And Savings

Initial required normalized fields after parsing:

- Posted date.
- Raw description.
- Amount.
- Source/account identity.
- Source file id.
- Source row number.

Initial likely review triggers:

- Possible internal transfer.
- Large transaction threshold.
- Uncategorized transaction.
- Duplicate-looking transaction.
- Missing/uncertain account identity.
- Payroll, deposit, or transfer rows that need income/transfer treatment.

Open owner/data confirmation:

- Confirm raw export columns.
- Confirm amount-sign conventions.
- Confirm whether balances are present.
- Confirm whether checking and savings exports share the same structure.

### Alliant Credit Card

Initial required normalized fields after parsing:

- Posted date.
- Raw description.
- Amount.
- Source/account identity.
- Source file id.
- Source row number.

Initial likely review triggers:

- Positive credits/refunds/payments.
- Interest or fee rows.
- Split-prone household/grocery merchants.
- Uncategorized transaction.
- Duplicate-looking transaction.
- Missing/uncertain account identity.

Open owner/data confirmation:

- Confirm raw export columns.
- Confirm amount-sign conventions for purchases, refunds, payments, fees, and interest.
- Confirm whether authorized/effective dates are available.

### Chase Prime Visa

Candidate required raw columns:

- `Transaction Date`
- `Post Date`
- `Description`
- `Category`
- `Type`
- `Amount`

Initial required normalized fields after parsing:

- Posted date from `Post Date`.
- Authorized/effective date from `Transaction Date`.
- Raw description from `Description`.
- Amount from `Amount`.
- Source/account identity.
- Source file id.
- Source row number.

Initial likely review triggers:

- Positive credits/refunds/payments.
- Amazon, Walmart, Costco, Target, and other split-prone merchants.
- Payment apps.
- Food delivery.
- Travel/reimbursement candidates.
- Interest or fee rows.
- Uncategorized transaction.
- Ambiguous duplicates.

Open owner/data confirmation:

- Confirm current Chase export columns match the candidate profile.
- Confirm amount-sign conventions for purchases, refunds, payments, fees, and interest.
- Confirm account identity handling without committing full account identifiers.

## Quarantine Behavior

Files should enter quarantine when:

- They cannot be read.
- They are unsupported file types for v1.
- Source/account identity is unknown or conflicting.
- Required columns are missing.
- Required row fields cannot be parsed.
- Blocking duplicate ambiguity exists at file or batch acceptance time.
- The owner explicitly sends a file to quarantine from the UI.

Quarantine record should include:

- Original filename.
- Stored quarantine path.
- File hash.
- Detected source/account if any.
- Blocking validation codes.
- Human-readable reason.
- Recovery options.
- Timestamp.

Rules:

- Quarantine is not deletion.
- Quarantine should preserve evidence.
- A quarantined file can be retried after settings/profile changes, but retry creates a new job and preserves prior validation history.

## Review Queue Outputs

Validation should feed the UI review queues with:

- Missing required source.
- Stale source.
- Blocking file validation.
- Warning file validation.
- Duplicate risk.
- Ambiguous source/account identity.
- Unusual row counts.
- Amount/date parsing concerns.
- Accepted-with-warning imports.

Review queue items should link back to:

- Source file record.
- Import job.
- Import batch when available.
- Affected rows when available.
- Validation finding code.

## Acceptance Rules

### Accept File Into Import Batch

Allowed only when:

- File hash is recorded.
- Source/account identity is known or explicitly owner-confirmed.
- Required profile columns are present.
- Required row fields parse.
- Imported row identities are unique within the file.
- No blocking file-level validations remain open.

### Accept Import Batch Into Operational State

Allowed only when:

- All included files have validation results.
- Batch-level validations have run.
- Ambiguous duplicate candidates are resolved or explicitly blocked from acceptance.
- Row counts and date ranges are recorded.
- Accepted warnings are acknowledged.
- The import creates immutable imported facts and does not overwrite prior facts.

### Mark Reports Provisional

Required when:

- Any required source is stale or missing.
- Any warning validation affects a report input.
- Review exposure crosses the later approved threshold.
- Source/account identity was owner-confirmed but not fully profile-validated.

### Block Monthly Close

Required when:

- Any required source is missing for the close period.
- Any required source is stale for the close period.
- Any blocking validation finding remains open.
- Duplicate ambiguity could affect close totals.
- Import validation has not run for all required sources.

## Validation Summary Artifact

Every import batch should be able to produce a human-readable validation summary.

Minimum summary content:

- Import batch id.
- Job id.
- Sources included.
- Files included.
- File hashes.
- Row counts by file/source.
- Transaction date min/max by source.
- Validation counts by severity.
- Open blocking findings.
- Open warning findings.
- Accepted warnings.
- Duplicate/overlap summary.
- Stale/missing source summary.
- Result: accepted, accepted with warnings, blocked, quarantined, or superseded.

Export formats later:

- Markdown for owner review.
- CSV/JSON for audit and downstream analysis.

No validation summary should contain raw credentials, account secrets, or unnecessary full account identifiers.

## Implementation Planning Inputs

Before parser implementation starts, implementation planning should capture:

- Header-only or synthetic samples for each required source profile.
- Synthetic rows covering purchases, refunds, payments, fees, transfers, malformed dates, malformed amounts, duplicate candidates, missing fields, and overlapping exports.
- Source/account metadata strategy that avoids storing unnecessary full account identifiers.
- Validation code enum/list.
- Parser versioning convention.
- Import job lifecycle states.
- Exact resolution actions for validation findings.

## Explicit Non-Goals

- No bank aggregator integration.
- No stored credentials.
- No browser automation.
- No PDF parsing.
- No vendor item import.
- No app implementation.
- No database schema.
- No migration of old normalized CSV outputs.
- No migration of old raw exports.
- No silent dedupe.
- No reports that ignore validation status.

## Owner Review Questions

Recommended default: approve this contract as the v1 validation baseline, with Alliant raw-column confirmation deferred until header-only or synthetic source samples are available.

Questions for review:

- Should accepted warnings require a note, or is explicit acknowledgment enough for v1?
- Should stale source be blocking for report generation or only for final monthly close?
- Should source/account identity confirmation be a one-time setting event or required per unknown file?
- Should v1 allow importing a single source when other required sources are missing, as long as reports remain provisional?
