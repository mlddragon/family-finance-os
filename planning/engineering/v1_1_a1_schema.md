# A1 Schema Engineering Spec

## Purpose

Define the v1.1 schema additions for migration `0009+` so Phase 1 and downstream tracks can implement funds, spendable, auth, goals, splits, receipts, budget targets, net worth, and snapshots against one shared contract.

The schema extends the approved four-layer model:

- Evidence layer remains source files on disk plus metadata in existing tables.
- Operational state adds planning records, snapshots, auth records, and receipt metadata.
- Decision/event layer remains append-only through `decision_events`, `settings_events`, `permission_state_events`, and `elevated_mode_events`.
- Derived/output layer gains spendable snapshots for monthly close and dashboard/report reproducibility.

## Non-goals

- No application code, ORM model code, API route code, seed data, or runtime artifacts in this doc.
- No real household data or prototype data migration.
- No separate projects table in v1.1; PRD projects map to `financial_goals.goal_type`.
- No per-user ledger partitions; users share one household ledger.
- No database trigger for transaction split sum validation. Split sum validation is app-layer validation so error payloads can be explicit and testable.
- No storage of raw receipt images/PDFs/blobs in SQLite. Files remain under external `DATA_ROOT`; SQLite stores metadata and paths.

## Migration Plan

Recommended sequence:

- `0009_v1_1_finance_planning_core`
  - `fund_pools`
  - `pool_category_links`
  - `monthly_pool_commitments`
  - `financial_goals`
  - `budget_targets`
  - `transaction_allocations`
  - `net_worth_snapshots`
  - `receipts`
  - `receipt_line_items`
  - `manual_obligations`
  - `spendable_balance_snapshots`
- `0010_v1_1_auth_core`
  - `users`
  - `user_sessions`
  - `totp_secrets`
  - `recovery_codes`

If implementation review prefers one migration, auth tables may be included in `0009`, but the preferred split keeps finance data and security-sensitive auth easier to review.

All tables use the existing `TimestampedModel` convention:

| Column | Type | Nullable | Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | UUID text primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |

## Schema/API Touchpoints

- A2 spendable reads liquid balances from `canonical_transactions`/`imported_rows`, settings/source profiles, `financial_goals`, `manual_obligations`, and writes `spendable_balance_snapshots`.
- B1 funds reads/writes `fund_pools`, `pool_category_links`, `monthly_pool_commitments`, `financial_goals`, and `budget_targets`.
- B2 splits writes `transaction_allocations` linked to `canonical_transactions`.
- B3 net worth writes `net_worth_snapshots`.
- D1 receipts writes `receipts` and `receipt_line_items` linked to `canonical_transactions`.
- A3 auth writes `users`, `user_sessions`, `totp_secrets`, and `recovery_codes`.
- Existing `decision_events` remains the audit spine for user-approved financial changes.

## UI Touchpoints

Mockup screen IDs:

- `home`: Spendable balance, provisional exposure, card obligation, fund commitment summary.
- `funds`: Fund pools, fund commitments, pool remaining, reserved goal balance.
- `dashboard`: Pool target progress and net worth actual/estimate toggle.
- `split`: Transaction allocation editor.
- `receipt`: Receipt and line-item capture.
- `export`: Analyst export contents.
- `auth` stage with `data-auth="login"` and `data-auth="enroll"`: authentication and first-boot enrollment.

## Table Definitions

### `fund_pools`

Purpose: Named planning containers used for Fund pool, Fund commitment, and Pool remaining.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `pool_key` | `String(120)` | no | Stable local identifier. Unique. |
| `name` | `String(160)` | no | Display label. Must not be blank at app layer. |
| `description` | `Text` | yes | Optional notes. |
| `status` | `String(40)` | no | `active`, `paused`, `archived`. |
| `sort_order` | `Integer` | no | UI ordering. |
| `rollover_policy` | `String(40)` | no | `none`, `carry_remaining`, `carry_deficit`. Default should be `none` unless B1 approves rollover behavior. |
| `created_by_user_id` | `String(36)` | yes | FK to `users.id`; nullable for pre-auth/system seed. |
| `updated_by_user_id` | `String(36)` | yes | FK to `users.id`; nullable for pre-auth/system seed. |

Constraints and indexes:

- `UniqueConstraint("pool_key")`.
- Index `ix_fund_pools_status_sort` on `status`, `sort_order`.
- FK `created_by_user_id -> users.id` after `0010`; if migrations split, add FK in `0010` or leave as soft reference and document why.
- FK `updated_by_user_id -> users.id` same as above.

### `pool_category_links`

Purpose: Map controlled categories to fund pools for default pool assignment and pool remaining calculations.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `fund_pool_id` | `String(36)` | no | FK to `fund_pools.id`. |
| `category_id` | `String(36)` | no | FK to `categories.id`. |
| `subcategory_key` | `String(120)` | yes | Optional controlled subcategory selector. |
| `link_type` | `String(40)` | no | `default`, `override`, `reporting_only`. |
| `active` | `Boolean` | no | Default `true`. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- `UniqueConstraint("fund_pool_id", "category_id", "subcategory_key")`.
- Index `ix_pool_category_links_category_active` on `category_id`, `active`.
- Index `ix_pool_category_links_pool_active` on `fund_pool_id`, `active`.
- FK `fund_pool_id -> fund_pools.id`.
- FK `category_id -> categories.id`.

### `monthly_pool_commitments`

Purpose: Store Fund commitment amounts per pool and month.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `fund_pool_id` | `String(36)` | no | FK to `fund_pools.id`. |
| `month` | `String(7)` | no | `YYYY-MM`. |
| `committed_amount` | `Numeric(14, 2)` | no | Non-negative app-layer validation. |
| `funding_source` | `String(80)` | no | `income`, `cash_reserve`, `manual_adjustment`, `rollover`. |
| `status` | `String(40)` | no | `draft`, `active`, `superseded`. |
| `decision_event_id` | `String(36)` | yes | Optional link to `decision_events.id` for auditable user change. |
| `notes` | `Text` | yes | User note. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- `UniqueConstraint("fund_pool_id", "month", "status")` with service rule allowing only one `active` commitment per pool/month.
- Index `ix_monthly_pool_commitments_month_status` on `month`, `status`.
- FK `fund_pool_id -> fund_pools.id`.
- Soft FK `decision_event_id -> decision_events.id`; Alembic FK optional because existing table has no ORM relationship yet.

### `financial_goals`

Purpose: Single v1.1 entity for goals/projects/sinking funds per D7. Goal name is required.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `goal_key` | `String(120)` | no | Stable local identifier. Unique. |
| `name` | `String(160)` | no | Required by DB and app. App must reject blank/whitespace. |
| `goal_type` | `String(40)` | no | `emergency`, `sinking_fund`, `purchase`, `other`. |
| `target_amount` | `Numeric(14, 2)` | no | Must be `>= 0` at app layer. |
| `target_date` | `String(10)` | yes | Optional ISO date. |
| `linked_fund_pool_id` | `String(36)` | yes | FK to `fund_pools.id`. |
| `reserved_balance` | `Numeric(14, 2)` | no | Reserved goal balance. Must be `>= 0` at app layer. |
| `status` | `String(40)` | no | `active`, `paused`, `completed`, `archived`. |
| `notes` | `Text` | yes | Optional. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |
| `updated_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- `UniqueConstraint("goal_key")`.
- `CheckConstraint("length(trim(name)) > 0", name="ck_financial_goals_name_required")` where SQLite/Alembic compatibility permits. Also enforce in app tests.
- Index `ix_financial_goals_status_type` on `status`, `goal_type`.
- Index `ix_financial_goals_pool_status` on `linked_fund_pool_id`, `status`.
- FK `linked_fund_pool_id -> fund_pools.id`.

### `budget_targets`

Purpose: Category or pool targets used by Funds, Dashboard, reports, and analyst export.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `target_key` | `String(120)` | no | Stable local identifier. Unique. |
| `month` | `String(7)` | yes | Null means recurring/default target. |
| `target_scope` | `String(40)` | no | `category`, `fund_pool`, `goal`, `household`. |
| `category_id` | `String(36)` | yes | FK to `categories.id` when scope is `category`. |
| `fund_pool_id` | `String(36)` | yes | FK to `fund_pools.id` when scope is `fund_pool`. |
| `financial_goal_id` | `String(36)` | yes | FK to `financial_goals.id` when scope is `goal`. |
| `target_amount` | `Numeric(14, 2)` | no | Non-negative app-layer validation. |
| `warning_threshold_amount` | `Numeric(14, 2)` | yes | Optional warning threshold. |
| `hard_cap_amount` | `Numeric(14, 2)` | yes | Optional cap. |
| `review_threshold_amount` | `Numeric(14, 2)` | yes | Optional review trigger. |
| `status` | `String(40)` | no | `active`, `paused`, `superseded`, `archived`. |
| `notes` | `Text` | yes | Optional. |
| `decision_event_id` | `String(36)` | yes | Optional audit link. |

Constraints and indexes:

- `UniqueConstraint("target_key")`.
- Index `ix_budget_targets_month_scope_status` on `month`, `target_scope`, `status`.
- Index `ix_budget_targets_category_month` on `category_id`, `month`.
- Index `ix_budget_targets_pool_month` on `fund_pool_id`, `month`.
- App-layer invariant: exactly one of `category_id`, `fund_pool_id`, `financial_goal_id` is required when `target_scope` is `category`, `fund_pool`, or `goal`; all may be null for `household`.
- FK `category_id -> categories.id`.
- FK `fund_pool_id -> fund_pools.id`.
- FK `financial_goal_id -> financial_goals.id`.

### `transaction_allocations`

Purpose: Store explicit transaction splits. Splits drive reports, pool remaining, and targets.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `canonical_transaction_id` | `String(36)` | no | FK to `canonical_transactions.id`. |
| `allocation_group_id` | `String(36)` | no | UUID text shared by all lines in one split version. |
| `line_number` | `Integer` | no | 1-based line order. |
| `amount` | `Numeric(14, 2)` | no | Signed amount using canonical transaction sign convention. |
| `category_id` | `String(36)` | no | FK to `categories.id`. |
| `subcategory` | `String(120)` | yes | Optional controlled subcategory value. |
| `fund_pool_id` | `String(36)` | yes | Optional FK to `fund_pools.id`; default derived from category link if null. |
| `financial_goal_id` | `String(36)` | yes | Optional FK to `financial_goals.id`. |
| `memo` | `Text` | yes | Optional user note. |
| `source` | `String(40)` | no | `manual`, `receipt_promoted`, `import_heuristic`, `rule_suggestion`. |
| `status` | `String(40)` | no | `active`, `superseded`, `voided`. |
| `decision_event_id` | `String(36)` | yes | Link to append-only user decision. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- `UniqueConstraint("allocation_group_id", "line_number")`.
- Index `ix_transaction_allocations_txn_status` on `canonical_transaction_id`, `status`.
- Index `ix_transaction_allocations_pool_status` on `fund_pool_id`, `status`.
- Index `ix_transaction_allocations_category_status` on `category_id`, `status`.
- FK `canonical_transaction_id -> canonical_transactions.id`.
- FK `category_id -> categories.id`.
- FK `fund_pool_id -> fund_pools.id`.
- FK `financial_goal_id -> financial_goals.id`.
- App-layer validation: active allocation line amounts for one transaction must sum exactly to the canonical transaction amount after quantizing to cents. Store no partial active split.

### `net_worth_snapshots`

Purpose: Manual actual/estimate asset and liability snapshots for D6.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `snapshot_date` | `String(10)` | no | ISO date. |
| `asset_or_liability` | `String(20)` | no | `asset` or `liability`. |
| `account_name` | `String(160)` | no | Display label; no account numbers. |
| `institution` | `String(160)` | yes | Optional. Must not store account numbers. |
| `category` | `String(80)` | no | Example: `liquid_cash`, `retirement`, `home`, `vehicle`, `consumer_debt`, `mortgage`, `other`. |
| `subcategory` | `String(120)` | yes | Optional. |
| `balance` | `Numeric(14, 2)` | no | Signed or positive-by-type? Implementer must choose one convention and document in B3; recommended positive amount with type determining rollup sign. |
| `valuation_method` | `String(40)` | no | `actual` or `estimate`. |
| `confidence` | `String(40)` | no | `high`, `medium`, `low`. Required for estimates; actual defaults to `high`. |
| `source_notes` | `Text` | yes | Required for estimates at app layer. |
| `include_in_actual_net_worth` | `Boolean` | no | True only for actual balances by default. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- Index `ix_net_worth_snapshots_date_method` on `snapshot_date`, `valuation_method`.
- Index `ix_net_worth_snapshots_category_date` on `category`, `snapshot_date`.
- App-layer validation: estimates require `confidence`, `snapshot_date`, and `source_notes`; estimates never feed Spendable balance.

### `receipts`

Purpose: Receipt header records linked to canonical ledger transactions as enrichment.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `canonical_transaction_id` | `String(36)` | yes | FK to `canonical_transactions.id`; nullable for unmatched receipt queue. |
| `merchant_name` | `String(255)` | no | Receipt merchant label. |
| `purchase_date` | `String(10)` | no | ISO date. |
| `receipt_total` | `Numeric(14, 2)` | no | Positive receipt total. |
| `currency` | `String(3)` | no | Default `USD`. |
| `source_type` | `String(40)` | no | `manual`, `csv_import`, `vendor_scraper`. |
| `source_file_id` | `String(36)` | yes | FK to `source_files.id` if imported from a file. |
| `stored_artifact_path` | `Text` | yes | Path under `DATA_ROOT` for optional local artifact. No repo paths. |
| `status` | `String(40)` | no | `draft`, `active`, `matched`, `needs_review`, `archived`. |
| `review_status` | `String(40)` | no | `unreviewed`, `needs_review`, `reviewed`. |
| `applied_as_split_decision_event_id` | `String(36)` | yes | Set only after explicit promote-to-split action. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- Index `ix_receipts_transaction_status` on `canonical_transaction_id`, `status`.
- Index `ix_receipts_purchase_date` on `purchase_date`.
- Index `ix_receipts_source_type_status` on `source_type`, `status`.
- FK `canonical_transaction_id -> canonical_transactions.id`.
- FK `source_file_id -> source_files.id`.
- App-layer validation: no raw receipt image/PDF in SQLite; local files must stay under `DATA_ROOT`.

### `receipt_line_items`

Purpose: Itemized receipt rows. They enrich transactions until explicitly promoted to splits.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `receipt_id` | `String(36)` | no | FK to `receipts.id`. |
| `line_number` | `Integer` | no | 1-based line order. |
| `item_description` | `Text` | no | User/vendor item text. |
| `quantity` | `Numeric(14, 4)` | yes | Optional. |
| `unit_price` | `Numeric(14, 2)` | yes | Optional. |
| `line_total` | `Numeric(14, 2)` | no | Positive line total. |
| `category_id` | `String(36)` | yes | Optional reviewed category. |
| `subcategory` | `String(120)` | yes | Optional. |
| `fund_pool_id` | `String(36)` | yes | Optional suggested pool. |
| `tax_relevant_candidate` | `Boolean` | no | Default `false`. |
| `reimbursement_candidate` | `Boolean` | no | Default `false`. |
| `business_candidate` | `Boolean` | no | Default `false`. |
| `review_status` | `String(40)` | no | `unreviewed`, `needs_review`, `reviewed`. |
| `metadata_json` | `Text` | yes | Vendor-specific enrichment details. |

Constraints and indexes:

- `UniqueConstraint("receipt_id", "line_number")`.
- Index `ix_receipt_line_items_receipt` on `receipt_id`.
- Index `ix_receipt_line_items_category_review` on `category_id`, `review_status`.
- FK `receipt_id -> receipts.id`.
- FK `category_id -> categories.id`.
- FK `fund_pool_id -> fund_pools.id`.
- App-layer validation: line item totals do not drive reports until promoted to `transaction_allocations`.

### `manual_obligations`

Purpose: User-entered upcoming obligations subtracted from Spendable balance per D1.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `obligation_key` | `String(120)` | no | Stable local identifier. Unique. |
| `name` | `String(160)` | no | Display label. |
| `amount` | `Numeric(14, 2)` | no | Non-negative app-layer validation. |
| `due_date` | `String(10)` | yes | ISO date. |
| `month` | `String(7)` | yes | `YYYY-MM` planning period. |
| `status` | `String(40)` | no | `active`, `paid`, `waived`, `archived`. |
| `obligation_type` | `String(40)` | no | `bill`, `loan_payment`, `manual_hold`, `other`. |
| `linked_canonical_transaction_id` | `String(36)` | yes | FK when obligation is satisfied by a transaction. |
| `notes` | `Text` | yes | Optional. |
| `created_by_user_id` | `String(36)` | yes | User attribution when available. |

Constraints and indexes:

- `UniqueConstraint("obligation_key")`.
- Index `ix_manual_obligations_month_status` on `month`, `status`.
- Index `ix_manual_obligations_due_status` on `due_date`, `status`.
- FK `linked_canonical_transaction_id -> canonical_transactions.id`.

### `spendable_balance_snapshots`

Purpose: Immutable-ish calculated snapshots for monthly close and reporting reproducibility.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `month` | `String(7)` | no | `YYYY-MM`. |
| `snapshot_type` | `String(40)` | no | `live`, `draft_close`, `final_close`. |
| `headline_spendable` | `Numeric(14, 2)` | no | Verified liquid cash - reserved goals - manual obligations by default. |
| `verified_liquid_cash` | `Numeric(14, 2)` | no | Sum of configured liquid balances. |
| `reserved_goal_balance` | `Numeric(14, 2)` | no | Sum active goal reserved balances. |
| `manual_obligations_total` | `Numeric(14, 2)` | no | Sum active upcoming obligations. |
| `provisional_exposure` | `Numeric(14, 2)` | no | Unreviewed outflows. |
| `include_provisional` | `Boolean` | no | Whether headline includes provisional exposure in this snapshot. |
| `card_obligation` | `Numeric(14, 2)` | no | Outstanding credit card obligation shown separately. |
| `confidence` | `String(40)` | no | `current`, `provisional`, `stale`, `blocked`. |
| `input_summary_json` | `Text` | no | Source keys, transaction ids/counts, settings version, warning codes. |
| `monthly_close_id` | `String(36)` | yes | FK to `monthly_closes.id` when captured in close. |
| `created_by_user_id` | `String(36)` | yes | User attribution or system user. |

Constraints and indexes:

- Index `ix_spendable_snapshots_month_type` on `month`, `snapshot_type`.
- Index `ix_spendable_snapshots_close` on `monthly_close_id`.
- FK `monthly_close_id -> monthly_closes.id`.
- Service rule: `final_close` snapshots should not be mutated; corrections create a revised close/snapshot.

### `users`

Purpose: Local household user records. Permissions control actions, not data silos.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `username` | `String(120)` | no | Local login name. Unique, normalized lowercase. |
| `display_name` | `String(160)` | no | Audit/UI label. |
| `role` | `String(40)` | no | `viewer`, `contributor`, `administrator`; maps into permission personas. |
| `status` | `String(40)` | no | `pending_invitation`, `active`, `disabled`, `recovery_locked`. |
| `passphrase_hash` | `Text` | no | Argon2id encoded hash. |
| `passphrase_updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `totp_required` | `Boolean` | no | Default `true` for personal mode. |
| `recovery_required` | `Boolean` | no | Default `true` until recovery kit acknowledged. |
| `last_login_at` | `String(40)` | yes | UTC ISO timestamp. |
| `failed_login_count` | `Integer` | no | Reset on successful login. |
| `locked_until` | `String(40)` | yes | Optional rate-limit lockout. |
| `invited_by_user_id` | `String(36)` | yes | FK to `users.id`. |
| `invitation_token_hash` | `Text` | yes | Hashed one-time invitation token. |
| `invitation_expires_at` | `String(40)` | yes | UTC ISO timestamp. |

Constraints and indexes:

- `UniqueConstraint("username")`.
- Index `ix_users_status_role` on `status`, `role`.
- FK `invited_by_user_id -> users.id`.
- Security rule: never store raw passphrases, invitation tokens, TOTP secrets in plaintext, recovery code plaintext, or session tokens.

### `user_sessions`

Purpose: Server-side session records for HttpOnly cookie tokens.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `user_id` | `String(36)` | no | FK to `users.id`. |
| `session_token_hash` | `Text` | no | Hash of random session token. Unique. |
| `created_from` | `String(40)` | no | `login`, `recovery`, `dev_bypass`. |
| `last_seen_at` | `String(40)` | no | UTC ISO timestamp. |
| `idle_expires_at` | `String(40)` | no | 8h from last activity. |
| `absolute_expires_at` | `String(40)` | no | 7d max from creation. |
| `revoked_at` | `String(40)` | yes | UTC ISO timestamp. |
| `revoked_reason` | `String(120)` | yes | `logout`, `recovery_reset`, `admin_disable`, `expired`, etc. |
| `user_agent_hash` | `String(64)` | yes | Optional privacy-preserving binding. |
| `client_host` | `String(120)` | yes | Should be localhost for personal runtime. |

Constraints and indexes:

- `UniqueConstraint("session_token_hash")`.
- Index `ix_user_sessions_user_active` on `user_id`, `revoked_at`, `absolute_expires_at`.
- Index `ix_user_sessions_idle_expiry` on `idle_expires_at`.
- FK `user_id -> users.id`.

### `totp_secrets`

Purpose: Store encrypted/locally protected TOTP seed metadata for users.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `user_id` | `String(36)` | no | FK to `users.id`. |
| `secret_ciphertext` | `Text` | no | Locally protected TOTP secret. Do not log. |
| `secret_version` | `Integer` | no | Rotation version. |
| `confirmed_at` | `String(40)` | yes | Set after first valid TOTP confirmation. |
| `disabled_at` | `String(40)` | yes | Set when replaced/disabled. |
| `last_used_counter` | `Integer` | yes | Optional replay defense. |

Constraints and indexes:

- Index `ix_totp_secrets_user_active` on `user_id`, `disabled_at`.
- FK `user_id -> users.id`.
- Service rule: one active confirmed TOTP secret per active user.

### `recovery_codes`

Purpose: One-time recovery codes for auth recovery and first-boot recovery kit.

| Column | Type | Nullable | Constraints/Notes |
| --- | --- | --- | --- |
| `id` | `String(36)` | no | Primary key. |
| `created_at` | `String(40)` | no | UTC ISO timestamp. |
| `updated_at` | `String(40)` | no | UTC ISO timestamp. |
| `user_id` | `String(36)` | no | FK to `users.id`. |
| `code_hash` | `Text` | no | Hash of recovery code. Unique. |
| `code_label` | `String(40)` | no | Display label such as `code_01`; no secret material. |
| `status` | `String(40)` | no | `active`, `used`, `revoked`. |
| `used_at` | `String(40)` | yes | UTC ISO timestamp. |
| `used_session_id` | `String(36)` | yes | FK to `user_sessions.id` if sign-in created a session. |
| `rotated_at` | `String(40)` | yes | UTC ISO timestamp when replaced. |

Constraints and indexes:

- `UniqueConstraint("code_hash")`.
- Index `ix_recovery_codes_user_status` on `user_id`, `status`.
- FK `user_id -> users.id`.
- FK `used_session_id -> user_sessions.id`.
- Security rule: plaintext codes are shown once during enrollment/regeneration and never stored.

## Relationship To Existing Tables

### `canonical_transactions`

- `transaction_allocations.canonical_transaction_id` links splits to canonical ledger transactions.
- `receipts.canonical_transaction_id` links receipt enrichment to canonical transactions.
- `manual_obligations.linked_canonical_transaction_id` marks obligations satisfied by imported transactions.
- Spendable and card obligation calculations read canonical transactions through reviewed/current state, never by mutating imported facts.

### `decision_events`

- Existing transaction review events remain authoritative for reviewed/current category state.
- v1.1 split creation/replacement should create decision events with stable `decision_type` values such as `transaction_split_replace`.
- Receipt promotion should create a decision event with a stable value such as `receipt_lines_promoted_to_splits`.
- Budget/fund/goal changes may either use dedicated tables plus `decision_event_id`, or settings events when configuration-like. The implementation doc for each track must choose one and stay consistent.

### `settings`

- Source profile settings continue to configure required sources and freshness.
- A2 may add settings for liquid account inclusion and provisional exposure default.
- A3 may add settings for QA dev bypass display and auth policy, but must not weaken personal runtime security by default.

## Rollback/Migration Notes

- Downgrade `0010` before `0009` if auth is split.
- Drop auth tables in order:
  1. `recovery_codes`
  2. `totp_secrets`
  3. `user_sessions`
  4. `users`
- Drop finance tables in order:
  1. `receipt_line_items`
  2. `receipts`
  3. `transaction_allocations`
  4. `spendable_balance_snapshots`
  5. `manual_obligations`
  6. `budget_targets`
  7. `financial_goals`
  8. `monthly_pool_commitments`
  9. `pool_category_links`
  10. `fund_pools`
  11. `net_worth_snapshots`
- Do not attempt to restore deleted financial-planning rows after downgrade. Downgrade is for development/test environments.
- Monthly close snapshots and receipt artifact files on disk are outside migration control; migrations remove only SQLite metadata.
- If user FK constraints create circular migration ordering, prefer nullable user attribution columns with documented soft references in `0009` and add FKs in `0010`.

## Test Plan

- Run Alembic upgrade from `0008_suggestions_approvals` to `head` on an empty SQLite DB.
- Run Alembic downgrade from `head` to `0008_suggestions_approvals`.
- Verify every new table has `id`, `created_at`, and `updated_at`.
- Verify indexes and unique constraints exist using SQLAlchemy inspector.
- Verify `financial_goals.name` rejects null and app service rejects blank/whitespace.
- Verify one active split group must sum to the canonical transaction amount in app-layer tests.
- Verify receipt line items do not affect reports until promoted to transaction allocations.
- Verify auth secrets are hash/ciphertext fields only; no plaintext token/code fields.
- Run existing API tests and security checks:
  - `python -m pytest -p no:cacheprovider`
  - `python scripts/check_sensitive_artifacts.py .`
  - `python scripts/check_secret_patterns.py .`
  - `python scripts/check_v1_security_contract.py .`

## Open Questions

None for schema shape. Implementation must still decide whether user attribution columns in `0009` are soft references until `0010` or hard FKs after splitting migrations; either is acceptable if documented in the migration PR.
