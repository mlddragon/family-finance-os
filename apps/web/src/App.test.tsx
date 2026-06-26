import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";
import { enUS } from "./locales/en-US";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage?.clear();
});

test("en-US locale covers primary UI surfaces", () => {
  expect(Object.keys(enUS.nav)).toEqual([
    "home",
    "sources",
    "validation",
    "review",
    "transactions",
    "reports",
    "settings",
  ]);
  expect(enUS.app.fallbackName).toBe("Family Finance OS");
  expect(enUS.review.other).toBe("Other");
});

const sourceProfiles = [
  {
    source_key: "alliant_checking",
    display_name: "Alliant Checking",
    account_type: "checking",
    required: false,
    freshness_threshold_days: 14,
    accepted_file_extensions: [".csv"],
    confirmation_status: "pending_owner_sample",
    is_template: true,
    enabled: false,
  },
  {
    source_key: "alliant_savings",
    display_name: "Alliant Savings",
    account_type: "savings",
    required: false,
    freshness_threshold_days: 14,
    accepted_file_extensions: [".csv"],
    confirmation_status: "pending_owner_sample",
    is_template: true,
    enabled: false,
  },
  {
    source_key: "chase_prime_visa",
    display_name: "Chase Prime Visa",
    account_type: "credit_card",
    required: false,
    freshness_threshold_days: 14,
    accepted_file_extensions: [".csv"],
    confirmation_status: "pending_owner_sample",
    is_template: true,
    enabled: false,
  },
];

const confirmedSourceProfiles = sourceProfiles.map((profile) =>
  profile.source_key === "chase_prime_visa"
    ? { ...profile, confirmation_status: "owner_confirmed_header_sample" }
    : profile,
);

const transaction = {
  id: "tx-1",
  posted_date: "2026-06-17",
  raw_description: "SYNTHETIC GROCERY",
  normalized_merchant: "synthetic grocery",
  amount: "12.34",
  initial_category: "Food",
  category_key_current: "groceries",
  category_display_name_current: "Groceries",
  category_current: "Groceries",
  review_status: "unreviewed",
  validation_status: "ready_for_review",
  imported_fact_count: 1,
};

const blockedTransaction = {
  ...transaction,
  id: "tx-2",
  raw_description: "SYNTHETIC DUPLICATE",
  amount: "12.34",
  initial_category: "Utilities",
  category_key_current: "utilities",
  category_display_name_current: "Utilities",
  category_current: "Utilities",
  validation_status: "blocked",
  imported_fact_count: 2,
};

const categories = [
  {
    id: "category-groceries",
    category_key: "groceries",
    display_name: "Groceries",
    category_type: "system",
    aliases: ["Food"],
    sort_order: 40,
    active: true,
  },
  {
    id: "category-utilities",
    category_key: "utilities",
    display_name: "Utilities",
    category_type: "system",
    aliases: [],
    sort_order: 30,
    active: true,
  },
  {
    id: "category-business",
    category_key: "business",
    display_name: "Business",
    category_type: "system",
    aliases: [],
    sort_order: 180,
    active: true,
  },
];

const personalRuntime = {
  app: "Family Finance OS",
  version: "0.3.0",
  local_only: true,
  bind_host: "127.0.0.1",
  app_env: "personal",
  app_env_label: "Personal data",
  dataset_kind: "personal",
  dev_mode: false,
  qa_controls_enabled: false,
  data_root: { path: "/tmp/Dillon_Finances_Data", exists: true },
  database: { status: "present", path: "/tmp/Dillon_Finances_Data/database/family_finance_os.sqlite3" },
};

const qaRuntime = {
  ...personalRuntime,
  app_env: "qa",
  app_env_label: "QA synthetic demo",
  dataset_kind: "synthetic",
  dev_mode: true,
  qa_controls_enabled: true,
  data_root: { path: "/tmp/Dillon_Finances_QA_Data", exists: true },
  database: { status: "present", path: "/tmp/Dillon_Finances_QA_Data/database/family_finance_os.sqlite3" },
};

const actorsPayload = {
  default_actor_key: "owner",
  human_actors: [
    {
      actor_key: "owner",
      actor_type: "human",
      display_name: "Owner",
      group_keys: ["administrator", "finance_manager"],
    },
  ],
  system_actors: [{ actor_key: "system", actor_type: "system", display_name: "System", group_keys: [] }],
  groups: [
    { group_key: "administrator", display_name: "Administrator" },
    { group_key: "finance_manager", display_name: "Finance Manager" },
  ],
  selectable_personas: [
    { persona_key: "finance_manager", persona_label: "Finance Manager", group_keys: ["finance_manager"] },
    { persona_key: "administrator", persona_label: "Administrator", group_keys: ["administrator"] },
  ],
  system_personas: [{ system_persona_key: "system:importer", display_name: "System: Importer" }],
};

function response(body: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => body,
  };
}

function errorResponse(status: number, code: string, message: string) {
  return {
    ok: false,
    status,
    json: async () => ({ detail: { code, message } }),
  };
}

function pathFor(input: RequestInfo | URL) {
  if (typeof input === "string") {
    return input.split("?")[0];
  }
  if (input instanceof URL) {
    return input.pathname;
  }
  return new URL(input.url).pathname;
}

function urlFor(input: RequestInfo | URL) {
  if (typeof input === "string") {
    return new URL(input, "http://localhost");
  }
  if (input instanceof URL) {
    return input;
  }
  return new URL(input.url);
}

function actorContextFromHeaders(init?: RequestInit) {
  const headers = init?.headers;
  if (!headers) {
    return null;
  }
  const raw =
    headers instanceof Headers
      ? headers.get("X-Actor-Context")
      : (headers as Record<string, string>)["X-Actor-Context"] ??
        (headers as Record<string, string>)["x-actor-context"];
  if (!raw) {
    return null;
  }
  return JSON.parse(raw) as { persona_key?: string };
}

function mockEffectivePermission(url: URL, init?: RequestInit) {
  const actionKey = url.searchParams.get("action_key") ?? "";
  const dataScopeKey = url.searchParams.get("data_scope_key") ?? "";
  const personaKey = actorContextFromHeaders(init)?.persona_key ?? "finance_manager";

  let allowed = personaKey === "finance_manager";
  let suggestion_allowed = false;

  if (personaKey === "administrator") {
    allowed = actionKey === "runtime.settings.manage";
  } else if (personaKey === "finance_contributor") {
    allowed = false;
    suggestion_allowed = actionKey === "review.decide";
  }

  return {
    allowed,
    suggestion_allowed,
    action_key: actionKey,
    data_scope_key: dataScopeKey,
    action_effect: allowed ? "allow" : suggestion_allowed ? "suggest" : "deny",
    scope_access: allowed ? "own" : suggestion_allowed ? "suggest" : "none",
    denied_reason: allowed || suggestion_allowed ? null : "default_matrix_denied",
  };
}

function mockPermissionPreview(body: { persona_key: string; action_key: string; data_scope_key: string }) {
  const url = new URL(`http://localhost/api/permissions/effective?action_key=${body.action_key}&data_scope_key=${body.data_scope_key}`);
  const evaluation = mockEffectivePermission(url, {
    headers: {
      "X-Actor-Context": JSON.stringify({ persona_key: body.persona_key }),
    },
  });
  return {
    persona_key: body.persona_key,
    ...evaluation,
  };
}

const inactiveElevatedModeStatus = {
  active: false,
  purpose_codes: {
    system_administration: [
      "user_group_permission_management",
      "source_or_system_settings",
      "maintenance_health_review",
      "runtime_troubleshooting",
    ],
    financial_governance: [
      "approval_rule_change",
      "governance_setting_change",
      "threshold_risk_rule_review",
      "monthly_close_governance_review",
    ],
  },
};

const emptySuggestionsPayload = {
  approval_mode_enabled: false,
  suggestions: [],
};

const emptyApprovalRequestsPayload = {
  approval_mode_enabled: false,
  approval_requests: [],
};

function installApiMock(options: { acceptImportError?: boolean; runtime?: typeof personalRuntime } = {}) {
  let importBatchVoided = false;
  let validationFindingCleared = false;
  const runtime = options.runtime ?? personalRuntime;
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = pathFor(input);
    const url = urlFor(input);
    if (path === "/api/permissions/effective") {
      return response(mockEffectivePermission(url, init));
    }
    if (path === "/api/elevated-mode/status") {
      return response(inactiveElevatedModeStatus);
    }
    if (path === "/api/elevated-mode/enter" && init?.method === "POST") {
      const body = JSON.parse(String(init.body));
      return response({
        active: true,
        session_id: "elevated-session-1",
        context: body.context,
        purpose_code: body.purpose_code,
        note: body.note,
        actor: body.actor,
        actor_context: body.actor_context,
        correlation_id: "corr-1",
        entered_at: "2026-06-18T00:00:00Z",
        last_activity_at: "2026-06-18T00:00:00Z",
        expires_at: "2026-06-18T00:15:00Z",
        purpose_codes: inactiveElevatedModeStatus.purpose_codes,
      });
    }
    if (path === "/api/elevated-mode/exit" && init?.method === "POST") {
      return response({ active: false });
    }
    if (path === "/api/elevated-mode/touch" && init?.method === "POST") {
      return response({
        active: true,
        session_id: "elevated-session-1",
        context: "system_administration",
        purpose_code: "source_or_system_settings",
        note: "Touch test",
        actor: "owner",
        entered_at: "2026-06-18T00:00:00Z",
        last_activity_at: "2026-06-18T00:05:00Z",
        expires_at: "2026-06-18T00:20:00Z",
        purpose_codes: inactiveElevatedModeStatus.purpose_codes,
      });
    }
    if (path === "/api/suggestions") {
      return response(emptySuggestionsPayload);
    }
    if (path.startsWith("/api/suggestions/") && init?.method === "POST") {
      return response({
        suggestion: {
          id: "suggestion-1",
          target_type: "canonical_transaction",
          target_id: "tx-1",
          action_key: "review.decide",
          decision_type: "category_change",
          field_name: "category",
          previous_value: "groceries",
          proposed_value: "business",
          status: "active",
          proposer_actor: "owner",
          suggestion_source: "user",
          notes: null,
          decision_event_id: null,
          approval_request_id: null,
          created_at: "2026-06-18T00:00:00Z",
          updated_at: "2026-06-18T00:00:00Z",
        },
      });
    }
    if (path === "/api/approval-requests") {
      return response(emptyApprovalRequestsPayload);
    }
    if (path.startsWith("/api/approval-requests/") && init?.method === "POST") {
      return response({
        approval_request: {
          id: "approval-1",
          target_type: "canonical_transaction",
          target_id: "tx-1",
          action_key: "review.decide",
          decision_type: "category_change",
          field_name: "category",
          previous_value: "groceries",
          proposed_value: "business",
          status: "approved",
          proposer_actor: "contributor",
          policy_trigger: "high_value",
          expires_at: "2026-07-02T00:00:00Z",
          source_suggestion_id: "suggestion-1",
          notes: null,
          applied_decision_event_id: "event-3",
          created_at: "2026-06-18T00:00:00Z",
          updated_at: "2026-06-18T00:01:00Z",
        },
      });
    }
    if (path === "/api/permissions/preview" && init?.method === "POST") {
      return response(mockPermissionPreview(JSON.parse(String(init.body))));
    }
    if (path === "/api/validation-findings/finding-warning/resolve" && init?.method === "POST") {
      validationFindingCleared = true;
      return response({
        finding: {
          id: "finding-warning",
          severity: "warning",
          code: "source_stale",
          target_type: "import_batch",
          target_id: "batch-1",
          message: "This source appears stale against its freshness threshold.",
          status: "resolved",
          created_at: "2026-06-18T00:00:01Z",
        },
      });
    }
    if (path === "/api/settings" && init?.method === "PATCH") {
      const patchBody = JSON.parse(String(init.body));
      const changedSetting = patchBody.changes?.[0];
      return response({
        tabs: ["Branding", "Data root", "Sources", "Categories", "Locale", "Operator", "Thresholds", "Reports", "Privacy", "Future integrations"],
        local_only: true,
        data_root: { path: "/tmp/Dillon_Finances_Data", exists: true },
        source_profiles: confirmedSourceProfiles,
        settings: [
          {
            id: "setting-branding",
            domain: "branding",
            setting_key: "branding.app_display_name",
            friendly_name: "App display name",
            value:
              changedSetting?.setting_key === "branding.app_display_name" ? changedSetting.value : "Family Finance OS",
            default_value: "Family Finance OS",
            changed_from_default: changedSetting?.setting_key === "branding.app_display_name",
            editable: true,
            note_required: false,
          },
          {
            id: "setting-operator",
            domain: "operator",
            setting_key: "operator.default_actor",
            friendly_name: "Default operator",
            value: "owner",
            default_value: "owner",
            changed_from_default: false,
            editable: true,
            note_required: false,
          },
          {
            id: "setting-1",
            domain: "privacy",
            setting_key: "runtime.local_only",
            friendly_name: "Local-only mode",
            value: true,
            default_value: true,
            changed_from_default: false,
            editable: false,
            note_required: true,
          },
          {
            id: "setting-2",
            domain: "sources",
            setting_key: "sources.chase_prime_visa.required",
            friendly_name: "Chase Prime Visa required",
            value: changedSetting?.setting_key === "sources.chase_prime_visa.required" ? changedSetting.value : true,
            default_value: false,
            changed_from_default:
              changedSetting?.setting_key === "sources.chase_prime_visa.required" ? changedSetting.value !== false : true,
            editable: true,
            note_required: true,
          },
        ],
        settings_events: [
          {
            id: "setting-event-2",
            domain: changedSetting?.domain ?? "sources",
            setting_key: changedSetting?.setting_key ?? "sources.chase_prime_visa.profile_confirmation_status",
            friendly_name:
              changedSetting?.setting_key === "sources.chase_prime_visa.required"
                ? "Chase Prime Visa required"
                : "Chase Prime Visa profile confirmation status",
            new_value: changedSetting?.value ?? "owner_confirmed_header_sample",
            actor: "owner",
            notes: changedSetting?.note ?? "Header-only source profile sample approved.",
            created_at: "2026-06-18T00:01:00Z",
          },
        ],
      });
    }
    if (path === "/api/import-batches/batch-1/validate" && init?.method === "POST") {
      return response({
        id: "batch-1",
        status: "validated",
        validation_status: "passed",
        row_count: 2,
        source_key: "chase_prime_visa",
        source_files: [],
        findings: [],
      });
    }
    if (path === "/api/import-batches/batch-1/accept" && init?.method === "POST") {
      if (options.acceptImportError) {
        return errorResponse(
          409,
          "warning_acknowledgment_required",
          "Warnings require explicit acknowledgment before acceptance.",
        );
      }
      return response({
        id: "batch-1",
        status: "accepted",
        validation_status: "accepted",
        row_count: 2,
        source_key: "chase_prime_visa",
        imported_rows_created: 2,
        canonical_transactions_created: 2,
      });
    }
    if (path === "/api/import-batches/batch-1/void" && init?.method === "POST") {
      importBatchVoided = true;
      return response({
        import_batch: {
          id: "batch-1",
          status: "voided",
          validation_status: "voided",
          row_count: 2,
          source_key: "chase_prime_visa",
          source_files: [
            {
              id: "file-1",
              original_filename: "SYNTHETIC_chase_summary.csv",
              validation_status: "voided",
              storage_status: "destroyed",
              row_count: 2,
            },
          ],
        },
      });
    }
    if (path === "/api/uploads" && init?.method === "POST") {
      return response({
        import_batch: {
          id: "uploaded-batch-1",
          status: "detected",
          validation_status: "pending",
          row_count: null,
          source_key: "alliant_savings",
          source_files: [],
        },
      });
    }
    if (path === "/api/decision-events" && init?.method === "POST") {
      const decisionBody = JSON.parse(String(init.body));
      return response({
        event: { id: "event-2", approved_value: decisionBody.approved_value },
        current_state:
          decisionBody.field_name === "category"
            ? {
                category_key_current: decisionBody.approved_value,
                category_display_name_current: "Business",
                category_current: "Business",
                review_status: "unreviewed",
              }
            : { category_current: "Groceries", review_status: "reviewed" },
      });
    }
    if (path === "/api/categories" && init?.method === "POST") {
      const categoryBody = JSON.parse(String(init.body));
      return response({
        category: {
          id: "category-family-project",
          category_key: "family_project",
          display_name: categoryBody.display_name,
          category_type: "custom",
          aliases: [],
          sort_order: 220,
          active: true,
        },
      });
    }
    if (path === "/api/reports/run" && init?.method === "POST") {
      return response({
        job: { id: "job-report", status: "completed" },
        report_run: { id: "report-run-1", status: "completed", validation_status: "passed_with_warnings" },
        validation_summary: { missing_required_count: 0 },
        artifacts: [
          {
            id: "artifact-report-1",
            artifact_type: "cashflow_summary",
            title: "Cashflow Summary",
            path: "/tmp/reports/cashflow_summary.json",
            download_url: "/api/artifacts/artifact-report-1/download",
          },
        ],
      });
    }
    if (path === "/api/monthly-close/draft" && init?.method === "POST") {
      return response({
        monthly_close: { id: "close-1", status: "draft", provisional: true },
        validation_summary: { missing_required_count: 0 },
        artifacts: [
          {
            id: "artifact-close-1",
            artifact_type: "monthly_close_manifest",
            title: "Monthly Close Manifest",
            path: "/tmp/monthly_close/manifest.json",
            download_url: "/api/artifacts/artifact-close-1/download",
          },
        ],
      });
    }
    if (path === "/api/exports/advisor" && init?.method === "POST") {
      return response({
        job: { id: "job-advisor", job_type: "advisor_export", status: "completed" },
        validation_summary: { missing_required_count: 0 },
        artifacts: [
          {
            id: "artifact-advisor-1",
            artifact_type: "advisor_summary",
            title: "Advisor Summary",
            path: "/tmp/exports/advisor_summary.json",
            download_url: "/api/artifacts/artifact-advisor-1/download",
          },
        ],
      });
    }

    const responses: Record<string, unknown> = {
      "/api/operator-summary": {
        runtime,
        latest_import: {
          id: "batch-1",
          status: "accepted",
          validation_status: "accepted",
          source_key: "chase_prime_visa",
          row_count: 2,
          transaction_date_max: "2026-06-17",
        },
        sources: {
          required_count: 0,
          missing_required_count: 0,
          imported_source_keys: ["chase_prime_visa"],
          profiles: sourceProfiles,
        },
        validation: {
          total_open: 2,
          open_blocking: 1,
          open_warning: 1,
          open_info: 0,
        },
        review: {
          total_transactions: 2,
          unreviewed: 2,
          reviewed: 0,
          blocked: 1,
        },
        monthly_close: {
          status: "not_started",
          ready_for_draft: false,
          ready_for_final: false,
          blockers: ["1 blocking validation finding"],
        },
        next_action: {
          code: "resolve_validation_blockers",
          label: "Resolve blocking validation findings",
        },
      },
      "/api/inbox/scan": {
        import_batches: [
          {
            id: "batch-1",
            status: importBatchVoided ? "voided" : "detected",
            validation_status: importBatchVoided ? "voided" : "pending",
            row_count: 2,
            source_key: "chase_prime_visa",
            source_files: [
              {
                id: "file-1",
                original_filename: "SYNTHETIC_chase_summary.csv",
                validation_status: importBatchVoided ? "voided" : "pending",
                storage_status: importBatchVoided ? "destroyed" : "present",
                row_count: 2,
              },
            ],
          },
        ],
      },
      "/api/validation-findings": {
        findings: [
          {
            id: "finding-1",
            severity: "blocking",
            code: "schema_mismatch",
            target_type: "import_batch",
            target_id: "batch-2",
            message: "File headers do not match an approved v1 source profile.",
            status: "open",
            created_at: "2026-06-18T00:00:00Z",
          },
          {
            id: "finding-warning",
            severity: "warning",
            code: "source_stale",
            target_type: "import_batch",
            target_id: "batch-1",
            message: "This source appears stale against its freshness threshold.",
            status: validationFindingCleared ? "resolved" : "open",
            created_at: "2026-06-18T00:00:01Z",
          },
        ],
      },
      "/api/transactions": {
        transactions: [transaction, blockedTransaction],
      },
      "/api/categories": {
        categories,
      },
      "/api/transactions/tx-1": {
        transaction: {
          ...transaction,
          imported_facts: [
            {
              id: "fact-1",
              raw_description: "SYNTHETIC GROCERY",
              initial_category: "Food",
              amount: "12.34",
            },
          ],
          decision_history_count: 1,
          decision_history: [
            {
              id: "event-1",
              decision_type: "category_change",
              field_name: "category",
              approved_value: "groceries",
              active: true,
              created_at: "2026-06-18T00:00:00Z",
            },
          ],
        },
      },
      "/api/transactions/tx-2": {
        transaction: {
          ...blockedTransaction,
          imported_facts: [],
          decision_history: [],
        },
      },
      "/api/settings": {
        tabs: ["Branding", "Data root", "Sources", "Categories", "Locale", "Operator", "Thresholds", "Reports", "Privacy", "Future integrations"],
        local_only: true,
        data_root: runtime.data_root,
        runtime,
        source_profiles: sourceProfiles,
        settings: [
          {
            id: "setting-branding",
            domain: "branding",
            setting_key: "branding.app_display_name",
            friendly_name: "App display name",
            value: "Family Finance OS",
            default_value: "Family Finance OS",
            changed_from_default: false,
            editable: true,
            note_required: false,
          },
          {
            id: "setting-operator",
            domain: "operator",
            setting_key: "operator.default_actor",
            friendly_name: "Default operator",
            value: "owner",
            default_value: "owner",
            changed_from_default: false,
            editable: true,
            note_required: false,
          },
          {
            id: "setting-1",
            domain: "privacy",
            setting_key: "runtime.local_only",
            friendly_name: "Local-only mode",
            value: true,
            default_value: true,
            changed_from_default: false,
            editable: false,
            note_required: true,
          },
          {
            id: "setting-2",
            domain: "sources",
            setting_key: "sources.chase_prime_visa.required",
            friendly_name: "Chase Prime Visa required",
            value: true,
            default_value: false,
            changed_from_default: true,
            editable: true,
            note_required: true,
          },
        ],
        settings_events: [
          {
            id: "setting-event-1",
            domain: "privacy",
            setting_key: "runtime.local_only",
            friendly_name: "Local-only mode",
            new_value: true,
            actor: "system",
            notes: "Seeded runtime local-only setting.",
            created_at: "2026-06-18T00:00:00Z",
          },
        ],
      },
      "/api/artifacts": {
        artifacts: [
          {
            id: "artifact-existing-1",
            artifact_type: "import_validation_summary",
            title: "Import And Validation Summary",
            path: "/tmp/reports/import_validation_summary.json",
            download_url: "/api/artifacts/artifact-existing-1/download",
          },
        ],
      },
      "/api/actors": actorsPayload,
    };

    return response(responses[path] ?? {});
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("renders operator home from API state", async () => {
  installApiMock();

  render(<App />);

  expect(screen.getByRole("heading", { name: "Family Finance OS" })).toBeInTheDocument();
  expect(await screen.findByText("Personal data")).toBeInTheDocument();
  expect(await screen.findByText("Local browser mode")).toBeInTheDocument();
  expect(await screen.findByText("Resolve blocking validation findings")).toBeInTheDocument();
  expect(screen.getByText("Open blockers")).toBeInTheDocument();
  expect(screen.getByText("Review queue")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Validation Issues" })).toBeInTheDocument();
});

test("shows persistent QA environment marker for synthetic runtime", async () => {
  installApiMock({ runtime: qaRuntime });

  render(<App />);

  expect(await screen.findByText("QA synthetic demo - not real financial data")).toBeInTheDocument();
  expect(screen.getByText("QA synthetic demo")).toBeInTheDocument();
  expect(screen.getByText("synthetic")).toBeInTheDocument();
});

test("renders local actor and persona selectors", async () => {
  installApiMock();

  render(<App />);

  const actorGroup = await screen.findByLabelText("Active local actor");
  await screen.findByRole("option", { name: "Administrator" });
  expect(within(actorGroup).getByLabelText("Actor")).toHaveValue("owner");
  expect(within(actorGroup).getByLabelText("Persona")).toHaveValue("finance_manager");

  fireEvent.change(within(actorGroup).getByLabelText("Persona"), { target: { value: "administrator" } });

  expect(window.localStorage.getItem("family-finance-os.activePersonaKey")).toBe("administrator");
});

test("navigates through the PR8 operator screens", async () => {
  installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Sources" }));
  expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
  expect(await screen.findByText("SYNTHETIC_chase_summary.csv")).toBeInTheDocument();
  expect(screen.getAllByText("Chase Prime Visa").length).toBeGreaterThan(0);
  expect(screen.getByText("Quarantine" )).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "Validation Issues" }));
  expect(await screen.findByRole("heading", { name: "Validation Issues" })).toBeInTheDocument();
  expect(screen.getByText("schema_mismatch")).toBeInTheDocument();
  expect(screen.getByText("Affected reports")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "Transactions" }));
  expect(await screen.findByRole("heading", { name: "Transactions" })).toBeInTheDocument();
  expect(screen.getByText("SYNTHETIC GROCERY")).toBeInTheDocument();
  expect(screen.getByText("Audit timeline")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "Reports" }));
  expect(await screen.findByRole("heading", { name: "Reports & Monthly Close" })).toBeInTheDocument();
  expect(await screen.findByText("Artifact registry")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
  expect(screen.getAllByText("Local-only mode").length).toBeGreaterThan(0);
  expect(screen.getByText("Settings audit history")).toBeInTheDocument();
});

test("sources screen validates and accepts import batches from the browser", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Sources" }));
  expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
  expect(await screen.findByText("SYNTHETIC_chase_summary.csv")).toBeInTheDocument();

  const validateButton = await screen.findByRole("button", { name: "Validate batch" });
  await waitFor(() => expect(validateButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Validate batch" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/import-batches/batch-1/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Batch validation completed")).toBeInTheDocument();

  const acceptButton = screen.getByRole("button", { name: "Accept batch" });
  await waitFor(() => expect(acceptButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Accept batch" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/import-batches/batch-1/accept",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Batch accepted")).toBeInTheDocument();
});

test("sources screen shows structured backend reasons when import acceptance is blocked", async () => {
  const fetchMock = installApiMock({ acceptImportError: true });

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Sources" }));
  expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
  expect(await screen.findByText("SYNTHETIC_chase_summary.csv")).toBeInTheDocument();

  const validateButton = await screen.findByRole("button", { name: "Validate batch" });
  await waitFor(() => expect(validateButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Validate batch" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/import-batches/batch-1/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Batch validation completed")).toBeInTheDocument();

  const acceptButton = screen.getByRole("button", { name: "Accept batch" });
  await waitFor(() => expect(acceptButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Accept batch" }));

  expect(
    await screen.findByText(
      "Batch acceptance blocked: Warnings require explicit acknowledgment before acceptance. (warning_acknowledgment_required)",
    ),
  ).toBeInTheDocument();
});

test("sources screen voids an upload with confirmation and optional file destruction", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Sources" }));
  expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
  expect(await screen.findByText("SYNTHETIC_chase_summary.csv")).toBeInTheDocument();

  const voidButton = screen.getByRole("button", { name: "Void upload" });
  await waitFor(() => expect(voidButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Void upload" }));
  const dialog = await screen.findByRole("dialog", { name: "Void upload" });
  const destroyCheckbox = screen.getByLabelText("Destroy stored files");
  expect(dialog).toBeInTheDocument();
  expect(destroyCheckbox).not.toBeChecked();

  fireEvent.change(screen.getByLabelText("Reason"), {
    target: { value: "Wrong export file uploaded" },
  });
  fireEvent.click(destroyCheckbox);
  fireEvent.click(screen.getByRole("button", { name: "Confirm void" }));

  await waitFor(() => {
    const voidCall = fetchMock.mock.calls.find(
      ([input, init]) => pathFor(input) === "/api/import-batches/batch-1/void" && init?.method === "POST",
    );
    expect(voidCall).toBeTruthy();
    const body = JSON.parse(String(voidCall?.[1]?.body));
    expect(body).toMatchObject({
      actor: "owner",
      actor_context: { actor_key: "owner", display_name: "Owner", persona_key: "finance_manager" },
      reason: "Wrong export file uploaded",
      destroy_files: true,
    });
  });
  expect(await screen.findByText("Upload voided and stored files destroyed")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Validate batch" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Accept batch" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Void upload" })).not.toBeInTheDocument();
});

test("sources upload sends selected source profile with the file", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Sources" }));
  expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
  await waitFor(() => expect(screen.getAllByText("Alliant Savings").length).toBeGreaterThan(0));

  const sourceProfileSelect = screen.getByLabelText("Source profile");
  fireEvent.change(sourceProfileSelect, {
    target: { value: "alliant_savings" },
  });
  await waitFor(() => expect(sourceProfileSelect).toHaveValue("alliant_savings"));

  const sourceFile = new File(["Date,Description,Amount,Balance\n"], "History-061926-011955.csv", { type: "text/csv" });
  const sourceFileInput = screen.getByLabelText("Source file") as HTMLInputElement;
  Object.defineProperty(sourceFileInput, "files", { value: [sourceFile], configurable: true });
  fireEvent.change(sourceFileInput);

  const uploadButton = screen.getByRole("button", { name: "Upload to inbox" });
  await waitFor(() => expect(uploadButton).not.toBeDisabled());
  fireEvent.submit(uploadButton.closest("form") as HTMLFormElement);

  await waitFor(() => {
    const uploadCall = fetchMock.mock.calls.find(([input, init]) => pathFor(input) === "/api/uploads" && init?.method === "POST");
    expect(uploadCall).toBeTruthy();
    const body = uploadCall?.[1]?.body;
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("source_key")).toBe("alliant_savings");
    expect((body as FormData).get("file")).toBeInstanceOf(File);
  });
  expect(await screen.findByText("File uploaded to inbox")).toBeInTheDocument();
});

test("validation screen clears acknowledged findings from the default open queue", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Validation Issues" }));
  expect(await screen.findByRole("heading", { name: "Validation Issues" })).toBeInTheDocument();
  expect(await screen.findByText("schema_mismatch")).toBeInTheDocument();
  expect(await screen.findByText("source_stale")).toBeInTheDocument();
  expect(screen.getByText("Active blockers must be fixed or voided before they can be cleared.")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Clear source_stale import_batch:batch-1" }));
  const dialog = await screen.findByRole("dialog", { name: "Clear validation finding" });
  expect(dialog).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Clear note"), {
    target: { value: "Acknowledged stale source while waiting for next export." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Confirm clear" }));

  await waitFor(() => {
    const clearCall = fetchMock.mock.calls.find(
      ([input, init]) => pathFor(input) === "/api/validation-findings/finding-warning/resolve" && init?.method === "POST",
    );
    expect(clearCall).toBeTruthy();
    expect(JSON.parse(String(clearCall?.[1]?.body))).toMatchObject({
      actor: "owner",
      actor_context: { actor_key: "owner", display_name: "Owner", persona_key: "finance_manager" },
      note: "Acknowledged stale source while waiting for next export.",
    });
  });
  expect(await screen.findByText("Validation finding cleared")).toBeInTheDocument();
  await waitFor(() => expect(screen.queryByText("source_stale")).not.toBeInTheDocument());

  fireEvent.click(screen.getByLabelText("Show cleared"));
  expect(await screen.findByText("source_stale")).toBeInTheDocument();
  expect(screen.getByText("resolved")).toBeInTheDocument();
});

test("review controls are labelled, focusable, and save append-only decisions", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Review" }));
  expect(await screen.findByText("SYNTHETIC GROCERY")).toBeInTheDocument();

  const approvedCategory = screen.getByLabelText("Approved category");
  approvedCategory.focus();
  expect(approvedCategory).toHaveFocus();
  expect(approvedCategory).toBeInstanceOf(HTMLSelectElement);
  const categoryOptions = Array.from((approvedCategory as HTMLSelectElement).options).map((option) => option.text);
  expect(categoryOptions).toEqual(["Groceries", "Utilities", "Business", "Other"]);

  fireEvent.change(approvedCategory, { target: { value: "business" } });
  await waitFor(() => expect(approvedCategory).toHaveValue("business"));

  const saveButton = screen.getByRole("button", { name: "Save decision" });
  await waitFor(() => expect(saveButton).not.toBeDisabled());
  saveButton.focus();
  expect(saveButton).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/decision-events",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Decision saved" )).toBeInTheDocument();
  const decisionCalls = fetchMock.mock.calls.filter((call) => pathFor(call[0]) === "/api/decision-events");
  expect(JSON.parse(decisionCalls.at(-1)?.[1]?.body as string)).toMatchObject({
    target_type: "canonical_transaction",
    target_id: "tx-1",
    decision_type: "category_change",
    field_name: "category",
    approved_value: "business",
    actor: "owner",
    explicit_user_action: true,
    notes: null,
  });
});

test("review save approves unchanged category as a reviewed decision", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Review" }));
  expect(await screen.findByText("SYNTHETIC GROCERY")).toBeInTheDocument();

  const approvedCategory = screen.getByLabelText("Approved category");
  expect(approvedCategory).toHaveValue("groceries");

  const saveReviewButton = screen.getByRole("button", { name: "Save decision" });
  await waitFor(() => expect(saveReviewButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/decision-events",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Decision saved")).toBeInTheDocument();
  const decisionCalls = fetchMock.mock.calls.filter((call) => pathFor(call[0]) === "/api/decision-events");
  expect(JSON.parse(decisionCalls.at(-1)?.[1]?.body as string)).toMatchObject({
    target_type: "canonical_transaction",
    target_id: "tx-1",
    decision_type: "review_status_change",
    field_name: "review_status",
    approved_value: "reviewed",
    actor: "owner",
    explicit_user_action: true,
  });
});

test("blocked validation filter selects blocked transaction and explains review save is blocked", async () => {
  installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Review" }));
  expect(await screen.findByText("SYNTHETIC GROCERY")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Validation status"), { target: { value: "blocked" } });

  expect(await screen.findByText("SYNTHETIC DUPLICATE")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("Current category")).toHaveValue("Utilities"));
  expect(screen.getByText("Blocked transactions must be resolved in Validation Issues before review decisions can be saved.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Resolve validation first" })).toBeDisabled();
});

test("reports screen runs artifacts and close/export actions", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Reports" }));
  expect(await screen.findByRole("heading", { name: "Reports & Monthly Close" })).toBeInTheDocument();
  expect(await screen.findByText("Import And Validation Summary")).toBeInTheDocument();

  const runReportsButton = screen.getByRole("button", { name: "Run reports" });
  await waitFor(() => expect(runReportsButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Run reports" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/reports/run",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Reports completed")).toBeInTheDocument();

  const draftCloseButton = screen.getByRole("button", { name: "Draft close" });
  await waitFor(() => expect(draftCloseButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Draft close" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/monthly-close/draft",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Draft close created" )).toBeInTheDocument();

  const advisorExportButton = screen.getByRole("button", { name: "Advisor export" });
  await waitFor(() => expect(advisorExportButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Advisor export" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/exports/advisor",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Advisor export created")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute(
    "href",
    "/api/artifacts/artifact-existing-1/download",
  );
});

test("settings screen saves source profile sample confirmation with owner note", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
  expect(await screen.findByText("Parser sample confirmation needed")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Source profile"), {
    target: { value: "chase_prime_visa" },
  });
  fireEvent.change(screen.getByLabelText("Owner confirmation note"), {
    target: { value: "Header-only Chase Prime Visa sample approved." },
  });
  const confirmSourceButton = screen.getByRole("button", { name: "Confirm source sample" });
  await waitFor(() => expect(confirmSourceButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Confirm source sample" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings",
      expect.objectContaining({ method: "PATCH" }),
    );
  });
  expect(await screen.findByText("Source confirmation saved")).toBeInTheDocument();
  const settingsPatchCall = fetchMock.mock.calls.find(
    (call) => pathFor(call[0]) === "/api/settings" && call[1]?.method === "PATCH",
  );
  expect(JSON.parse(settingsPatchCall?.[1]?.body as string)).toMatchObject({
    actor: "owner",
    changes: [
      {
        domain: "sources",
        setting_key: "sources.chase_prime_visa.profile_confirmation_status",
        value: "owner_confirmed_header_sample",
        note: "Header-only Chase Prime Visa sample approved.",
      },
    ],
  });
});

test("settings screen edits editable database-backed settings with required notes", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();

  fireEvent.change(await screen.findByLabelText("Editable setting"), {
    target: { value: "sources.chase_prime_visa.required" },
  });
  fireEvent.change(screen.getByLabelText("Setting value"), {
    target: { value: "false" },
  });
  fireEvent.change(screen.getByLabelText("Change note"), {
    target: { value: "Temporarily make Chase Prime Visa optional for v1 smoke testing." },
  });
  const saveSettingButton = screen.getByRole("button", { name: "Save setting" });
  await waitFor(() => expect(saveSettingButton).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "Save setting" }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings",
      expect.objectContaining({ method: "PATCH" }),
    );
  });
  expect(await screen.findByText("Setting saved")).toBeInTheDocument();
  const settingsPatchCalls = fetchMock.mock.calls.filter(
    (call) => pathFor(call[0]) === "/api/settings" && call[1]?.method === "PATCH",
  );
  expect(JSON.parse(settingsPatchCalls.at(-1)?.[1]?.body as string)).toMatchObject({
    actor: "owner",
    changes: [
      {
        domain: "sources",
        setting_key: "sources.chase_prime_visa.required",
        value: false,
        note: "Temporarily make Chase Prime Visa optional for v1 smoke testing.",
      },
    ],
  });
});

test("settings screen defaults to editable friendly settings with defaults and audit notes", async () => {
  installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();

  const editableSetting = await screen.findByLabelText("Editable setting");
  expect(Array.from((editableSetting as HTMLSelectElement).options).map((option) => option.text)).toEqual([
    "App display name",
    "Default operator",
    "Chase Prime Visa required",
  ]);

  const activeSettingsPanel = screen.getByText("Active settings").closest("section");
  expect(activeSettingsPanel).not.toBeNull();
  const activeSettings = within(activeSettingsPanel as HTMLElement);
  const activeSettingsTable = within(activeSettings.getByRole("table"));
  expect(activeSettingsTable.getByRole("columnheader", { name: "Friendly name" })).toBeInTheDocument();
  expect(activeSettingsTable.getByRole("columnheader", { name: "Value" })).toBeInTheDocument();
  expect(activeSettingsTable.getByRole("columnheader", { name: "Default Value" })).toBeInTheDocument();
  expect(activeSettingsTable.getByText("App display name")).toBeInTheDocument();
  expect(activeSettingsTable.getByText("Chase Prime Visa required")).toBeInTheDocument();
  expect(activeSettingsTable.queryByText("runtime.local_only")).not.toBeInTheDocument();
  expect(activeSettingsTable.queryByText("Local-only mode")).not.toBeInTheDocument();
  expect(screen.getAllByText("Family Finance OS").length).toBeGreaterThan(0);
  expect(screen.getByText("Seeded runtime local-only setting.")).toBeInTheDocument();

  fireEvent.click(screen.getByLabelText("Show read-only settings"));
  expect(activeSettingsTable.getByText("Local-only mode")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("Show setting key column"));
  expect(activeSettingsTable.getByRole("columnheader", { name: "Setting key" })).toBeInTheDocument();
  expect(activeSettingsTable.getByText("runtime.local_only")).toBeInTheDocument();
});
