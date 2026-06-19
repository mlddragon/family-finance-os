import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

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
    source_key: "alliant_savings",
    display_name: "Alliant Savings",
    account_type: "savings",
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
  category_current: "Food",
  review_status: "unreviewed",
  validation_status: "ready_for_review",
  imported_fact_count: 1,
};

const blockedTransaction = {
  ...transaction,
  id: "tx-2",
  raw_description: "SYNTHETIC DUPLICATE",
  amount: "12.34",
  validation_status: "blocked",
  imported_fact_count: 2,
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
    return input;
  }
  if (input instanceof URL) {
    return input.pathname;
  }
  return new URL(input.url).pathname;
}

function installApiMock(options: { acceptImportError?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = pathFor(input);
    if (path === "/api/settings" && init?.method === "PATCH") {
      const patchBody = JSON.parse(String(init.body));
      const changedSetting = patchBody.changes?.[0];
      return response({
        tabs: ["Data root", "Sources", "Thresholds", "Reports", "Privacy", "Future integrations"],
        local_only: true,
        data_root: { path: "/tmp/Dillon_Finances_Data", exists: true },
        source_profiles: confirmedSourceProfiles,
        settings: [
          {
            id: "setting-1",
            domain: "privacy",
            setting_key: "runtime.local_only",
            value: true,
            editable: false,
            note_required: true,
          },
          {
            id: "setting-2",
            domain: "sources",
            setting_key: "sources.chase_prime_visa.required",
            value: changedSetting?.setting_key === "sources.chase_prime_visa.required" ? changedSetting.value : true,
            editable: true,
            note_required: true,
          },
        ],
        settings_events: [
          {
            id: "setting-event-2",
            domain: changedSetting?.domain ?? "sources",
            setting_key: changedSetting?.setting_key ?? "sources.chase_prime_visa.profile_confirmation_status",
            new_value: changedSetting?.value ?? "owner_confirmed_header_sample",
            actor: "mason",
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
      return response({
        event: { id: "event-2", approved_value: "Groceries" },
        current_state: { category_current: "Groceries", review_status: "unreviewed" },
      });
    }
    if (path === "/api/reports/run" && init?.method === "POST") {
      return response({
        job: { id: "job-report", status: "completed" },
        report_run: { id: "report-run-1", status: "completed", validation_status: "passed_with_warnings" },
        validation_summary: { missing_required_count: 3 },
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
        validation_summary: { missing_required_count: 3 },
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
        validation_summary: { missing_required_count: 3 },
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
          row_count: 2,
          transaction_date_max: "2026-06-17",
        },
        sources: {
          required_count: 4,
          missing_required_count: 3,
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
            status: "detected",
            validation_status: "pending",
            row_count: 2,
            source_key: "chase_prime_visa",
            source_files: [
              {
                id: "file-1",
                original_filename: "SYNTHETIC_chase_summary.csv",
                validation_status: "pending",
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
        ],
      },
      "/api/transactions": {
        transactions: [transaction, blockedTransaction],
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
              approved_value: "Food",
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
        tabs: ["Data root", "Sources", "Thresholds", "Reports", "Privacy", "Future integrations"],
        local_only: true,
        data_root: { path: "/tmp/Dillon_Finances_Data", exists: true },
        source_profiles: sourceProfiles,
        settings: [
          {
            id: "setting-1",
            domain: "privacy",
            setting_key: "runtime.local_only",
            value: true,
            editable: false,
            note_required: true,
          },
          {
            id: "setting-2",
            domain: "sources",
            setting_key: "sources.chase_prime_visa.required",
            value: true,
            editable: true,
            note_required: true,
          },
        ],
        settings_events: [
          {
            id: "setting-event-1",
            domain: "privacy",
            setting_key: "runtime.local_only",
            new_value: true,
            actor: "system",
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
    };

    return response(responses[path] ?? {});
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("renders operator home from API state", async () => {
  installApiMock();

  render(<App />);

  expect(screen.getByRole("heading", { name: "Dillon Finances" })).toBeInTheDocument();
  expect(await screen.findByText("Local browser mode")).toBeInTheDocument();
  expect(await screen.findByText("Resolve blocking validation findings")).toBeInTheDocument();
  expect(screen.getByText("Open blockers")).toBeInTheDocument();
  expect(screen.getByText("Review queue")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Validation Issues" })).toBeInTheDocument();
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
  expect(screen.getAllByText("runtime.local_only").length).toBeGreaterThan(0);
  expect(screen.getByText("Settings audit history")).toBeInTheDocument();
});

test("sources screen validates and accepts import batches from the browser", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Sources" }));
  expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
  expect(await screen.findByText("SYNTHETIC_chase_summary.csv")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Validate batch" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/import-batches/batch-1/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Batch validation completed")).toBeInTheDocument();

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

  fireEvent.click(screen.getByRole("button", { name: "Validate batch" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/import-batches/batch-1/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Batch validation completed")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Accept batch" }));

  expect(
    await screen.findByText(
      "Batch acceptance blocked: Warnings require explicit acknowledgment before acceptance. (warning_acknowledgment_required)",
    ),
  ).toBeInTheDocument();
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

test("review controls are labelled, focusable, and save append-only decisions", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Review" }));
  expect(await screen.findByText("SYNTHETIC GROCERY")).toBeInTheDocument();

  const approvedCategory = screen.getByLabelText("Approved category");
  approvedCategory.focus();
  expect(approvedCategory).toHaveFocus();
  fireEvent.change(approvedCategory, { target: { value: "Groceries" } });
  await waitFor(() => {
    expect(approvedCategory).toHaveValue("Groceries");
  });

  const saveButton = screen.getByRole("button", { name: "Save decision" });
  saveButton.focus();
  expect(saveButton).toHaveFocus();
  fireEvent.click(saveButton);

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
    approved_value: "Groceries",
    explicit_user_action: true,
  });
});

test("reports screen runs artifacts and close/export actions", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Reports" }));
  expect(await screen.findByRole("heading", { name: "Reports & Monthly Close" })).toBeInTheDocument();
  expect(await screen.findByText("Import And Validation Summary")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Run reports" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/reports/run",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Reports completed")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Draft close" }));
  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/monthly-close/draft",
      expect.objectContaining({ method: "POST" }),
    );
  });
  expect(await screen.findByText("Draft close created" )).toBeInTheDocument();

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
    actor: "mason",
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
    actor: "mason",
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
