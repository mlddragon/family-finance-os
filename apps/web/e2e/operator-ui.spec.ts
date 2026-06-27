import { expect, Page, test } from "@playwright/test";

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
    id: "category-family-project",
    category_key: "family_project",
    display_name: "Family Project",
    category_type: "custom",
    aliases: [],
    sort_order: 220,
    active: true,
  },
];

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

const personalRuntime = {
  app: "Family Finance OS",
  version: "0.5.0",
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
  purpose_requires_note: ["approval_rule_change"],
};

const fundsSummary = {
  month: "2026-06",
  spendable: {
    headline: "3412.58",
    verified_liquid_cash: "6180.00",
    reserved_goal_balance: "1900.00",
    manual_upcoming_obligations: "867.42",
    provisional_exposure: "112.00",
    card_obligation_total: "1523.23",
    card_obligation_items: [],
    includes_provisional: false,
    warnings: [],
  },
  commitment_health: {
    funded_this_month: "900.00",
    fund_commitments: "1000.00",
    pool_remaining_total: "146.50",
    uncommitted: "-100.00",
    overcommitted: true,
  },
  pools: [],
  goals: [],
  budget_targets: [],
};

const netWorthSummary = {
  include_estimates: false,
  latest_snapshot_date: "2026-06-30",
  actual: { assets: "1500.00", liabilities: "300.00", net_worth: "1200.00" },
  with_estimates: {
    assets: "9500.00",
    liabilities: "300.00",
    net_worth: "9200.00",
    includes_estimates: true,
  },
  series: [],
};

async function waitForMutatingControls(page: import("@playwright/test").Page) {
  await expect(page.getByRole("button", { name: "Validate batch" })).toBeEnabled({ timeout: 10_000 });
}

const authenticatedAuthStatus = {
  requires_owner_enrollment: false,
  authenticated: true,
  user: {
    id: "user-1",
    username: "owner",
    display_name: "SYNTHETIC Owner",
    role: "administrator",
    status: "active",
    totp_required: true,
    recovery_required: false,
  },
  session: {
    id: "session-1",
    created_from: "login",
    last_seen_at: "2026-06-18T00:00:00Z",
    idle_expires_at: "2026-06-18T08:00:00Z",
    absolute_expires_at: "2026-06-25T00:00:00Z",
  },
  qa_auth_bypass_available: false,
};

async function mockApi(
  page: Page,
  onDecision?: (payload: unknown) => void,
  onBatchAction?: (action: string, payload: unknown) => void,
  onSettingChange?: (payload: unknown) => void,
) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path === "/api/auth/status") {
      await route.fulfill({ json: authenticatedAuthStatus });
      return;
    }

    if (path === "/api/permissions/effective") {
      const actionKey = new URL(request.url()).searchParams.get("action_key") ?? "";
      const dataScopeKey = new URL(request.url()).searchParams.get("data_scope_key") ?? "";
      const actorContextHeader = request.headers()["x-actor-context"];
      const personaKey = actorContextHeader
        ? (JSON.parse(actorContextHeader) as { persona_key?: string }).persona_key ?? "finance_manager"
        : "finance_manager";
      await route.fulfill({
        json: {
          allowed: personaKey === "finance_manager",
          suggestion_allowed: false,
          action_key: actionKey,
          data_scope_key: dataScopeKey,
          action_effect: personaKey === "finance_manager" ? "allow" : "deny",
          scope_access: personaKey === "finance_manager" ? "own" : "none",
          denied_reason: personaKey === "finance_manager" ? null : "default_matrix_denied",
        },
      });
      return;
    }

    if (path === "/api/elevated-mode/status") {
      await route.fulfill({ json: inactiveElevatedModeStatus });
      return;
    }

    if (path === "/api/elevated-mode/enter" && request.method() === "POST") {
      const body = request.postDataJSON() as { context: string; purpose_code: string; note: string; actor: string };
      await route.fulfill({
        json: {
          active: true,
          session_id: "elevated-session-1",
          context: body.context,
          purpose_code: body.purpose_code,
          note: body.note,
          actor: body.actor,
          entered_at: "2026-06-18T00:00:00Z",
          last_activity_at: "2026-06-18T00:00:00Z",
          expires_at: "2026-06-18T00:15:00Z",
          purpose_codes: inactiveElevatedModeStatus.purpose_codes,
        },
      });
      return;
    }

    if (path === "/api/elevated-mode/exit" && request.method() === "POST") {
      await route.fulfill({ json: { active: false } });
      return;
    }

    if (path === "/api/elevated-mode/touch" && request.method() === "POST") {
      await route.fulfill({
        json: {
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
        },
      });
      return;
    }

    if (path === "/api/suggestions") {
      await route.fulfill({ json: { approval_mode_enabled: false, suggestions: [] } });
      return;
    }

    if (path.startsWith("/api/suggestions/") && request.method() === "POST") {
      await route.fulfill({
        json: {
          suggestion: {
            id: "suggestion-1",
            target_type: "canonical_transaction",
            target_id: "tx-1",
            action_key: "review.decide",
            decision_type: "category_change",
            field_name: "category",
            previous_value: "groceries",
            proposed_value: "family_project",
            status: "active",
            proposer_actor: "owner",
            suggestion_source: "user",
            notes: null,
            decision_event_id: null,
            approval_request_id: null,
            created_at: "2026-06-18T00:00:00Z",
            updated_at: "2026-06-18T00:00:00Z",
          },
        },
      });
      return;
    }

    if (path === "/api/approval-requests") {
      await route.fulfill({ json: { approval_mode_enabled: false, approval_requests: [] } });
      return;
    }

    if (path.startsWith("/api/approval-requests/") && request.method() === "POST") {
      await route.fulfill({
        json: {
          approval_request: {
            id: "approval-1",
            target_type: "canonical_transaction",
            target_id: "tx-1",
            action_key: "review.decide",
            decision_type: "category_change",
            field_name: "category",
            previous_value: "groceries",
            proposed_value: "family_project",
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
        },
      });
      return;
    }

    if (path === "/api/permissions/preview" && request.method() === "POST") {
      const body = request.postDataJSON() as { persona_key: string; action_key: string; data_scope_key: string };
      const allowed = body.persona_key === "finance_manager";
      await route.fulfill({
        json: {
          persona_key: body.persona_key,
          allowed,
          suggestion_allowed: body.persona_key === "finance_contributor" && body.action_key === "review.decide",
          action_key: body.action_key,
          data_scope_key: body.data_scope_key,
          action_effect: allowed ? "allow" : "deny",
          scope_access: allowed ? "own" : "none",
          denied_reason: allowed ? null : "default_matrix_denied",
        },
      });
      return;
    }

    if (path === "/api/settings" && request.method() === "PATCH") {
      const payload = request.postDataJSON();
      onSettingChange?.(payload);
      await route.fulfill({
        json: {
          tabs: ["Branding", "Data root", "Sources", "Categories", "Locale", "Operator", "Thresholds", "Reports", "Privacy", "Future integrations"],
          local_only: true,
          data_root: personalRuntime.data_root,
          runtime: personalRuntime,
          source_profiles: sourceProfiles,
          settings: [
            {
              id: "setting-branding",
              domain: "branding",
              setting_key: "branding.app_display_name",
              value: "Family Finance OS",
              editable: true,
              note_required: false,
            },
            {
              id: "setting-operator",
              domain: "operator",
              setting_key: "operator.default_actor",
              value: "owner",
              editable: true,
              note_required: false,
            },
            {
              id: "setting-1",
              domain: "sources",
              setting_key: "sources.chase_prime_visa.required",
              value: false,
              editable: true,
              note_required: true,
            },
          ],
          settings_events: [
            {
              id: "setting-event-1",
              domain: "sources",
              setting_key: "sources.chase_prime_visa.required",
              new_value: false,
              actor: "owner",
              created_at: "2026-06-18T00:00:00Z",
            },
          ],
        },
      });
      return;
    }

    if (path === "/api/import-batches/batch-1/validate") {
      onBatchAction?.("validate", request.postDataJSON());
      await route.fulfill({
        json: {
          id: "batch-1",
          status: "validated",
          validation_status: "passed",
          row_count: 1,
          source_key: "chase_prime_visa",
          source_files: [],
          findings: [],
        },
      });
      return;
    }

    if (path === "/api/import-batches/batch-1/accept") {
      onBatchAction?.("accept", request.postDataJSON());
      await route.fulfill({
        json: {
          id: "batch-1",
          status: "accepted",
          validation_status: "accepted",
          row_count: 1,
          source_key: "chase_prime_visa",
          source_files: [],
        },
      });
      return;
    }

    if (path === "/api/decision-events") {
      const payload = request.postDataJSON();
      onDecision?.(payload);
      await route.fulfill({
        json: {
          event: { id: "event-2" },
          current_state: {
            category_key_current: payload.approved_value,
            category_display_name_current: "Family Project",
            category_current: "Family Project",
            review_status: "unreviewed",
          },
        },
      });
      return;
    }

    if (path === "/api/categories" && request.method() === "POST") {
      await route.fulfill({
        json: {
          category: categories[1],
        },
      });
      return;
    }

    const responses: Record<string, unknown> = {
      "/api/operator-summary": {
        runtime: personalRuntime,
        latest_import: {
          id: "batch-1",
          status: "accepted",
          validation_status: "accepted",
          source_key: "chase_prime_visa",
          row_count: 1,
          transaction_date_max: "2026-06-17",
        },
        sources: {
          required_count: 0,
          missing_required_count: 0,
          imported_source_keys: ["chase_prime_visa"],
          profiles: sourceProfiles,
        },
        validation: {
          total_open: 1,
          open_blocking: 1,
          open_warning: 0,
          open_info: 0,
        },
        review: {
          total_transactions: 1,
          unreviewed: 1,
          reviewed: 0,
          blocked: 0,
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
      "/api/funds/summary": fundsSummary,
      "/api/net-worth/summary": netWorthSummary,
      "/api/inbox/scan": {
        import_batches: [
          {
            id: "batch-1",
            status: "detected",
            validation_status: "pending",
            row_count: 1,
            source_key: "chase_prime_visa",
            source_files: [
              {
                id: "file-1",
                original_filename: "SYNTHETIC_chase_summary.csv",
                validation_status: "pending",
                row_count: 1,
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
        ],
      },
      "/api/transactions": { transactions: [transaction] },
      "/api/categories": { categories },
      "/api/transactions/tx-1": {
        transaction: {
          ...transaction,
          imported_facts: [],
          decision_history: [],
        },
      },
      "/api/settings": {
        tabs: ["Branding", "Data root", "Sources", "Categories", "Locale", "Operator", "Thresholds", "Reports", "Privacy", "Future integrations"],
        local_only: true,
        data_root: personalRuntime.data_root,
        runtime: personalRuntime,
        source_profiles: sourceProfiles,
        settings: [
          {
            id: "setting-branding",
            domain: "branding",
            setting_key: "branding.app_display_name",
            value: "Family Finance OS",
            editable: true,
            note_required: false,
          },
          {
            id: "setting-operator",
            domain: "operator",
            setting_key: "operator.default_actor",
            value: "owner",
            editable: true,
            note_required: false,
          },
          {
            id: "setting-1",
            domain: "sources",
            setting_key: "sources.chase_prime_visa.required",
            value: true,
            editable: true,
            note_required: true,
          },
        ],
        settings_events: [],
      },
      "/api/artifacts": {
        artifacts: [
          {
            id: "artifact-existing-1",
            artifact_type: "import_validation_summary",
            title: "Import And Validation Summary",
            path: "/tmp/reports/import_validation_summary.json",
            sensitivity: "financial_sensitive",
            download_url: "/api/artifacts/artifact-existing-1/download",
          },
        ],
      },
      "/api/actors": actorsPayload,
    };

    await route.fulfill({ json: responses[path] ?? {} });
  });
}

test("navigates operator screens and shows local-only status", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
  await page.waitForResponse(
    (response) => response.url().includes("/api/operator-summary") && response.ok(),
  );

  await expect(page.getByText("Local browser mode")).toBeVisible();
  await expect(page.getByText("Resolve blocking validation findings", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Sources" }).click();
  await expect(page.getByRole("heading", { name: "Sources", exact: true })).toBeVisible();
  await expect(page.getByText("SYNTHETIC_chase_summary.csv")).toBeVisible();

  await page.getByRole("link", { name: "Validation Issues" }).click();
  await expect(page.getByText("schema_mismatch")).toBeVisible();

  await page.getByRole("link", { name: "Reports" }).click();
  await expect(page.getByRole("heading", { name: "Reports & Monthly Close" })).toBeVisible();
  await expect(page.getByText("Artifact registry")).toBeVisible();
  await expect(page.getByText("Import And Validation Summary")).toBeVisible();
});

test("saves a category decision through the browser flow", async ({ page }) => {
  let decisionPayload: unknown;
  await mockApi(page, (payload) => {
    decisionPayload = payload;
  });
  await page.goto("/");

  await page.getByRole("link", { name: "Review" }).click();
  await expect(page.getByRole("cell", { name: "SYNTHETIC GROCERY" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save decision" })).toBeEnabled();
  await page.getByLabel("Approved category").selectOption("__other__");
  await page.getByLabel("Other category").fill("Family Project");
  await page.getByLabel("Notes").fill("Creating a new category from the browser review flow.");
  await page.getByRole("button", { name: "Save decision" }).click();

  await expect(page.getByText("Decision saved")).toBeVisible();
  expect(decisionPayload).toMatchObject({
    target_type: "canonical_transaction",
    target_id: "tx-1",
    decision_type: "category_change",
    field_name: "category",
    approved_value: "family_project",
    actor: "owner",
    actor_context: { actor_key: "owner", display_name: "Owner", persona_key: "finance_manager" },
    explicit_user_action: true,
    notes: "Creating a new category from the browser review flow.",
  });
});

test("validates and accepts an import batch through the browser flow", async ({ page }) => {
  const batchActions: Array<{ action: string; payload: unknown }> = [];
  await mockApi(page, undefined, (action, payload) => {
    batchActions.push({ action, payload });
  });
  await page.goto("/");

  await page.getByRole("link", { name: "Sources" }).click();
  await expect(page.getByText("SYNTHETIC_chase_summary.csv")).toBeVisible();
  await waitForMutatingControls(page);
  await page.getByRole("button", { name: "Validate batch" }).click();
  await expect(page.getByText("Batch validation completed")).toBeVisible();
  await page.getByRole("button", { name: "Accept batch" }).click();
  await expect(page.getByText("Batch accepted")).toBeVisible();

  expect(batchActions).toEqual([
    { action: "validate", payload: null },
    { action: "accept", payload: { acknowledge_warnings: false } },
  ]);
});

test("saves an editable setting through the browser flow", async ({ page }) => {
  let settingsPayload: unknown;
  await mockApi(page, undefined, undefined, (payload) => {
    settingsPayload = payload;
  });
  await page.goto("/");

  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByRole("button", { name: "Save setting" })).toBeEnabled();
  await page.getByLabel("Editable setting").selectOption("sources.chase_prime_visa.required");
  await page.getByLabel("Setting value").selectOption("false");
  await page.getByLabel("Change note").fill("Temporarily optional for v1 browser smoke testing.");
  await page.getByRole("button", { name: "Save setting" }).click();

  await expect(page.getByText("Setting saved")).toBeVisible();
  expect(settingsPayload).toMatchObject({
    actor: "owner",
    actor_context: { actor_key: "owner", display_name: "Owner", persona_key: "finance_manager" },
    changes: [
      {
        domain: "sources",
        setting_key: "sources.chase_prime_visa.required",
        value: false,
        note: "Temporarily optional for v1 browser smoke testing.",
      },
    ],
  });
});
