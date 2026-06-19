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

function pathFor(input: RequestInfo | URL) {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.pathname;
  }
  return new URL(input.url).pathname;
}

function installApiMock() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = pathFor(input);
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
            status: "accepted",
            validation_status: "accepted",
            row_count: 2,
            source_key: "chase_prime_visa",
            source_files: [
              {
                id: "file-1",
                original_filename: "SYNTHETIC_chase_summary.csv",
                validation_status: "accepted",
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
  expect(await screen.findByText("Chase Prime Visa")).toBeInTheDocument();
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

test("review controls are labelled, focusable, and save append-only decisions", async () => {
  const fetchMock = installApiMock();

  render(<App />);

  fireEvent.click(screen.getByRole("link", { name: "Review" }));
  expect(await screen.findByText("SYNTHETIC GROCERY")).toBeInTheDocument();

  const approvedCategory = screen.getByLabelText("Approved category");
  approvedCategory.focus();
  expect(approvedCategory).toHaveFocus();
  fireEvent.change(approvedCategory, { target: { value: "Groceries" } });

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
  const decisionCall = fetchMock.mock.calls.find((call) => pathFor(call[0]) === "/api/decision-events");
  expect(JSON.parse(decisionCall?.[1]?.body as string)).toMatchObject({
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
