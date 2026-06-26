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
  source: "local_selector" | "system" | "compat_actor_string";
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
