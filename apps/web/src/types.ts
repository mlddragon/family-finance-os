export type RuntimeStatus = {
  app: string;
  version: string;
  local_only: boolean;
  bind_host: string;
  data_root: {
    path: string;
    exists: boolean;
  };
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
  category_current: string | null;
  review_status: string;
  validation_status: string;
  imported_fact_count?: number;
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
    active: boolean;
    created_at: string;
  }>;
};

export type SettingsPayload = {
  tabs: string[];
  local_only: boolean;
  data_root: RuntimeStatus["data_root"];
  settings: Array<{
    id: string;
    domain: string;
    setting_key: string;
    value: unknown;
    editable: boolean;
    note_required: boolean;
  }>;
  settings_events: Array<{
    id: string;
    domain: string;
    setting_key: string;
    new_value: unknown;
    actor: string;
    created_at: string;
  }>;
  source_profiles: SourceProfile[];
};

export type DecisionEventResponse = {
  event: {
    id: string;
  };
  current_state?: {
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
