export type RuntimeStatus = {
  app: string;
  version: string;
  local_only: boolean;
  bind_host: string;
  app_env: "personal" | "qa";
  app_env_label: string;
  dataset_kind: "personal" | "synthetic";
  dev_mode: boolean;
  qa_controls_enabled: boolean;
  data_root: {
    path: string;
    exists: boolean;
  };
  database?: {
    status: string;
    path: string;
  };
};

export type ActorContext = {
  actor_key: string;
  actor_type: "human" | "system";
  display_name: string;
  persona_key?: string;
  persona_label?: string;
  group_keys: string[];
  system_persona_key?: string;
  source: "local_selector" | "system" | "compat_actor_string" | "auth_session" | "recovery" | "dev_bypass";
};

export type AuthStatus = {
  requires_owner_enrollment: boolean;
  authenticated: boolean;
  user: null | {
    id: string;
    username: string;
    display_name: string;
    role: string;
    status: string;
    totp_required: boolean;
    recovery_required: boolean;
  };
  session: null | {
    id: string;
    created_from: string;
    last_seen_at: string;
    idle_expires_at: string;
    absolute_expires_at: string;
  };
  qa_auth_bypass_available: boolean;
};

export type ActorsPayload = {
  default_actor_key: string;
  human_actors: Array<{
    actor_key: string;
    actor_type: "human";
    display_name: string;
    group_keys: string[];
  }>;
  system_actors: Array<{
    actor_key: string;
    actor_type: "system";
    display_name: string;
    group_keys: string[];
  }>;
  groups: Array<{ group_key: string; display_name: string }>;
  selectable_personas: Array<{ persona_key: string; persona_label: string; group_keys: string[] }>;
  system_personas: Array<{ system_persona_key: string; display_name: string }>;
};

export type SourceProfile = {
  source_key: string;
  display_name: string;
  account_type: string;
  required: boolean;
  freshness_threshold_days: number;
  accepted_file_extensions: string[];
  expected_headers?: string[];
  amount_sign_policy?: string;
  parser_version?: string;
  confirmation_status: string;
  is_template?: boolean;
  enabled?: boolean;
  template_required_default?: boolean;
  imported?: boolean;
  latest_import_status?: string;
  latest_transaction_date?: string | null;
};

export type OperatorSummary = {
  runtime: RuntimeStatus;
  latest_import: {
    id: string | null;
    status: string;
    validation_status: string;
    source_key: string | null;
    row_count: number;
    transaction_date_min?: string | null;
    transaction_date_max?: string | null;
    created_at?: string | null;
  };
  sources: {
    required_count: number;
    imported_source_keys: string[];
    missing_required_count: number;
    missing_required_source_keys?: string[];
    profiles: SourceProfile[];
  };
  validation: {
    total_open: number;
    open_blocking: number;
    open_warning: number;
    open_info: number;
    by_severity?: Record<string, number>;
  };
  review: {
    total_transactions: number;
    unreviewed: number;
    reviewed: number;
    blocked: number;
  };
  monthly_close: {
    status: string;
    ready_for_draft: boolean;
    ready_for_final: boolean;
    blockers: string[];
  };
  artifacts?: {
    generated_count: number;
    status: string;
  };
  inbox?: {
    tracked_file_count: number;
  };
  next_action: {
    code: string;
    label: string;
  };
};

export type SpendableSummary = {
  headline: string;
  verified_liquid_cash: string;
  reserved_goal_balance: string;
  manual_upcoming_obligations: string;
  provisional_exposure: string;
  card_obligation_total: string;
  card_obligation_items: Array<{
    card: string;
    owed: string | null;
    note: string;
    source_key?: string;
    status?: string;
  }>;
  includes_provisional: boolean;
  confidence?: string;
  warnings?: Array<{ code: string; severity: string; message: string }>;
};

export type FundPoolSummary = {
  id: string;
  pool_key: string;
  name: string;
  description: string | null;
  status: string;
  sort_order: number;
  rollover_policy: string;
  commitment: string;
  spent: string;
  pool_remaining: string;
  created_at?: string;
  updated_at?: string;
};

export type FundPool = FundPoolSummary & {
  pool_remaining?: string;
  spent?: string;
  commitment?: string;
};

export type FundCommitment = {
  id: string;
  fund_pool_id: string;
  fund_pool_name: string | null;
  month: string;
  committed_amount: string;
  funding_source: string;
  status: string;
  decision_event_id: string | null;
  notes: string | null;
  created_at?: string;
  updated_at?: string;
};

export type FinancialGoal = {
  id: string;
  goal_key: string;
  name: string;
  goal_type: "emergency" | "sinking_fund" | "purchase" | "other" | string;
  target_amount: string;
  target_date: string | null;
  linked_fund_pool_id: string | null;
  reserved_balance: string;
  remaining_to_target: string;
  status: string;
  notes: string | null;
};

export type BudgetTarget = {
  id: string;
  target_key: string;
  month: string | null;
  target_scope: string;
  category_id: string | null;
  fund_pool_id: string | null;
  financial_goal_id: string | null;
  target_amount: string;
  warning_threshold_amount: string | null;
  hard_cap_amount: string | null;
  review_threshold_amount: string | null;
  status: string;
  notes: string | null;
  decision_event_id: string | null;
};

export type FundsSummary = {
  month: string;
  spendable: SpendableSummary;
  commitment_health: {
    funded_this_month: string;
    fund_commitments: string;
    pool_remaining_total: string;
    uncommitted: string;
    overcommitted: boolean;
  };
  pools: Array<FundPoolSummary & { status: "On track" | "Not started" | string }>;
  goals: FinancialGoal[];
  budget_targets: BudgetTarget[];
};

export type NetWorthRollup = {
  assets: string;
  liabilities: string;
  net_worth: string;
};

export type NetWorthSummary = {
  include_estimates: boolean;
  latest_snapshot_date: string | null;
  actual: NetWorthRollup;
  with_estimates: NetWorthRollup & {
    includes_estimates: boolean;
  };
  series: Array<NetWorthRollup & {
    snapshot_date: string;
    includes_estimates: boolean;
  }>;
};

export type NetWorthSnapshot = {
  id: string;
  snapshot_date: string;
  asset_or_liability: "asset" | "liability" | string;
  account_name: string;
  institution: string | null;
  category: string;
  subcategory: string | null;
  balance: string;
  valuation_method: "actual" | "estimate" | string;
  confidence: "high" | "medium" | "low" | string;
  source_notes: string | null;
  include_in_actual_net_worth: boolean;
};

export type ImportBatch = {
  id: string;
  status: string;
  validation_status: string;
  row_count: number | null;
  source_key: string | null;
  source_files: SourceFile[];
};

export type SourceFile = {
  id: string;
  original_filename: string;
  stored_path?: string;
  file_sha256?: string;
  byte_size?: number;
  storage_status?: string;
  destroyed_at?: string | null;
  destroyed_by?: string | null;
  destroyed_reason?: string | null;
  validation_status: string;
  row_count: number | null;
  parser_version?: string | null;
};

export type InboxScan = {
  import_batches: ImportBatch[];
};

export type ValidationFinding = {
  id: string;
  severity: string;
  code: string;
  message: string;
  target_type: string;
  target_id: string | null;
  status: string;
  created_at: string;
};

export type Transaction = {
  id: string;
  posted_date?: string;
  raw_description: string | null;
  normalized_merchant?: string | null;
  amount: string;
  initial_category?: string | null;
  category_key_current?: string | null;
  category_display_name_current?: string | null;
  category_current: string | null;
  review_status: string;
  validation_status: string;
  imported_fact_count?: number;
};

export type Category = {
  id: string;
  category_key: string;
  display_name: string;
  category_type: "system" | "custom" | string;
  aliases: string[];
  sort_order: number;
  active: boolean;
};

export type TransactionDetail = Transaction & {
  imported_facts?: Array<{
    id: string;
    raw_description: string;
    initial_category?: string | null;
    amount: string;
  }>;
  decision_history_count?: number;
  decision_history?: Array<{
    id: string;
    decision_type: string;
    field_name: string;
    approved_value: string | null;
    actor?: string;
    actor_context?: ActorContext | null;
    notes?: string | null;
    active: boolean;
    created_at: string;
  }>;
};

export type TransactionAllocation = {
  id: string;
  canonical_transaction_id: string;
  allocation_group_id: string;
  line_number: number;
  amount: string;
  category_id: string;
  category_display_name: string | null;
  subcategory: string | null;
  fund_pool_id: string | null;
  fund_pool_name: string | null;
  financial_goal_id: string | null;
  financial_goal_name: string | null;
  memo: string | null;
  source: string;
  status: string;
  decision_event_id: string | null;
  created_at?: string;
  updated_at?: string;
};

export type TransactionAllocationsPayload = {
  transaction_id: string;
  allocations: TransactionAllocation[];
  summary: {
    transaction_amount: string;
    allocated: string;
    remainder: string;
    balanced: boolean;
    allocation_count: number;
  };
  event?: {
    id: string;
    decision_type?: string;
    field_name?: string;
  };
};

export type SettingsPayload = {
  tabs: string[];
  local_only: boolean;
  data_root: RuntimeStatus["data_root"];
  runtime?: RuntimeStatus;
  settings: Array<{
    id: string;
    domain: string;
    setting_key: string;
    friendly_name: string;
    value: unknown;
    default_value: unknown;
    changed_from_default: boolean;
    editable: boolean;
    note_required: boolean;
  }>;
  settings_events: Array<{
    id: string;
    domain: string;
    setting_key: string;
    friendly_name?: string;
    new_value: unknown;
    actor: string;
    actor_context?: ActorContext | null;
    notes?: string | null;
    created_at: string;
  }>;
  source_profiles: SourceProfile[];
};

export type DecisionEventResponse = {
  event: {
    id: string;
    actor_context?: ActorContext | null;
  };
  current_state?: {
    category_key_current?: string | null;
    category_display_name_current?: string | null;
    category_current?: string | null;
    review_status?: string;
  };
};

export type Artifact = {
  id: string;
  artifact_type: string;
  path: string;
  sha256?: string;
  byte_size?: number;
  title: string | null;
  description?: string | null;
  producing_job_id?: string | null;
  source_inputs?: unknown;
  retention_category?: string | null;
  sensitivity?: string;
  download_url: string;
  created_at?: string;
};

export type EffectivePermission = {
  allowed: boolean;
  suggestion_allowed: boolean;
  action_key: string;
  data_scope_key: string;
  action_effect: string | null;
  scope_access: string | null;
  denied_reason: string | null;
};

export type PermissionPreviewRequest = {
  persona_key: string;
  action_key: string;
  data_scope_key: string;
  scope_selector?: string | null;
};

export type PermissionPreviewResponse = EffectivePermission & {
  persona_key: string;
};

export type UIPermissionCheck = {
  id: string;
  label: string;
  action_key: string;
  data_scope_key: string;
};

export type ElevatedContext = "system_administration" | "financial_governance";

export type ElevatedModeStatus = {
  active: boolean;
  purpose_codes?: Record<ElevatedContext, string[]>;
  purpose_requires_note?: string[];
  session_id?: string;
  context?: ElevatedContext;
  purpose_code?: string;
  note?: string;
  actor?: string;
  actor_context?: ActorContext;
  correlation_id?: string;
  entered_at?: string;
  last_activity_at?: string;
  expires_at?: string;
};

export type Suggestion = {
  id: string;
  target_type: string;
  target_id: string;
  action_key: string;
  decision_type: string;
  field_name: string;
  previous_value: string | null;
  proposed_value: string;
  status: string;
  proposer_actor: string;
  proposer_actor_context?: ActorContext | null;
  suggestion_source: string;
  notes: string | null;
  decision_event_id: string | null;
  approval_request_id: string | null;
  created_at: string;
  updated_at: string;
};

export type SuggestionsPayload = {
  approval_mode_enabled: boolean;
  suggestions: Suggestion[];
};

export type ApprovalRequest = {
  id: string;
  target_type: string;
  target_id: string;
  action_key: string;
  decision_type: string;
  field_name: string;
  previous_value: string | null;
  proposed_value: string;
  status: string;
  proposer_actor: string;
  proposer_actor_context?: ActorContext | null;
  policy_trigger: string;
  expires_at: string;
  source_suggestion_id: string | null;
  notes: string | null;
  applied_decision_event_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ApprovalRequestsPayload = {
  approval_mode_enabled: boolean;
  approval_requests: ApprovalRequest[];
};

export type ArtifactActionResponse = {
  job?: {
    id: string;
    job_type?: string;
    status: string;
  };
  report_run?: {
    id: string;
    status: string;
    validation_status: string;
  };
  monthly_close?: {
    id: string;
    status: string;
    provisional: boolean;
  };
  validation_summary?: Record<string, unknown>;
  artifacts: Artifact[];
};
