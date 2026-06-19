import { expect, Page, test } from "@playwright/test";

const sourceProfiles = [
  {
    source_key: "alliant_checking",
    display_name: "Alliant Checking",
    account_type: "checking",
    required: true,
    freshness_threshold_days: 14,
    accepted_file_extensions: [".csv"],
    confirmation_status: "pending_owner_sample",
  },
  {
    source_key: "chase_prime_visa",
    display_name: "Chase Prime Visa",
    account_type: "credit_card",
    required: true,
    freshness_threshold_days: 14,
    accepted_file_extensions: [".csv"],
    confirmation_status: "pending_owner_sample",
  },
];

const transaction = {
  id: "tx-1",
  posted_date: "2026-06-17",
  raw_description: "SYNTHETIC GROCERY",
  normalized_merchant: "synthetic grocery",
  amount: "12.34",
  initial_category: "Food",
  category_current: "Food",
  review_status: "unreviewed",
  validation_status: "ready_for_review",
  imported_fact_count: 1,
};

async function mockApi(
  page: Page,
  onDecision?: (payload: unknown) => void,
  onBatchAction?: (action: string, payload: unknown) => void,
) {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

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
      onDecision?.(request.postDataJSON());
      await route.fulfill({
        json: {
          event: { id: "event-2" },
          current_state: { category_current: "Groceries", review_status: "unreviewed" },
        },
      });
      return;
    }

    const responses: Record<string, unknown> = {
      "/api/operator-summary": {
        runtime: {
          app: "Dillon Finances",
          version: "0.1.0",
          local_only: true,
          bind_host: "127.0.0.1",
          data_root: { path: "/tmp/Dillon_Finances_Data", exists: true },
        },
        latest_import: {
          id: "batch-1",
          status: "accepted",
          validation_status: "accepted",
          source_key: "chase_prime_visa",
          row_count: 1,
          transaction_date_max: "2026-06-17",
        },
        sources: {
          required_count: 4,
          missing_required_count: 3,
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
      "/api/transactions/tx-1": {
        transaction: {
          ...transaction,
          imported_facts: [],
          decision_history: [],
        },
      },
      "/api/settings": {
        tabs: ["Data root", "Sources", "Thresholds", "Reports", "Privacy", "Future integrations"],
        local_only: true,
        data_root: { path: "/tmp/Dillon_Finances_Data", exists: true },
        source_profiles: sourceProfiles,
        settings: [],
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
    };

    await route.fulfill({ json: responses[path] ?? {} });
  });
}

test("navigates operator screens and shows local-only status", async ({ page }) => {
  await mockApi(page);
  await page.goto("/");

  await expect(page.getByText("Local browser mode")).toBeVisible();
  await expect(page.getByText("Resolve blocking validation findings")).toBeVisible();

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
  await page.getByLabel("Approved category").fill("Groceries");
  await page.getByRole("button", { name: "Save decision" }).click();

  await expect(page.getByText("Decision saved")).toBeVisible();
  expect(decisionPayload).toMatchObject({
    target_type: "canonical_transaction",
    target_id: "tx-1",
    decision_type: "category_change",
    field_name: "category",
    approved_value: "Groceries",
    explicit_user_action: true,
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
  await page.getByRole("button", { name: "Validate batch" }).click();
  await expect(page.getByText("Batch validation completed")).toBeVisible();
  await page.getByRole("button", { name: "Accept batch" }).click();
  await expect(page.getByText("Batch accepted")).toBeVisible();

  expect(batchActions).toEqual([
    { action: "validate", payload: null },
    { action: "accept", payload: { acknowledge_warnings: false } },
  ]);
});
