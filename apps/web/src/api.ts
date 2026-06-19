import type {
  Artifact,
  ArtifactActionResponse,
  DecisionEventResponse,
  InboxScan,
  OperatorSummary,
  SettingsPayload,
  Transaction,
  TransactionDetail,
  ValidationFinding,
} from "./types";

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${path}`);
  }
  return response.json() as Promise<T>;
}

export function fetchOperatorSummary() {
  return apiJson<OperatorSummary>("/api/operator-summary");
}

export function scanInbox() {
  return apiJson<InboxScan>("/api/inbox/scan");
}

export function uploadSourceFile(file: File) {
  const body = new FormData();
  body.append("file", file);
  return apiJson<InboxScan>("/api/uploads", {
    method: "POST",
    body,
  });
}

export function fetchValidationFindings() {
  return apiJson<{ findings: ValidationFinding[] }>("/api/validation-findings");
}

export function fetchTransactions() {
  return apiJson<{ transactions: Transaction[] }>("/api/transactions");
}

export function fetchTransactionDetail(transactionId: string) {
  return apiJson<{ transaction: TransactionDetail }>(`/api/transactions/${transactionId}`);
}

export function saveCategoryDecision(payload: {
  transactionId: string;
  approvedCategory: string;
  notes?: string;
}) {
  return apiJson<DecisionEventResponse>("/api/decision-events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_type: "canonical_transaction",
      target_id: payload.transactionId,
      decision_type: "category_change",
      field_name: "category",
      proposed_value: payload.approvedCategory,
      approved_value: payload.approvedCategory,
      actor: "mason",
      suggestion_source: "owner",
      explicit_user_action: true,
      notes: payload.notes?.trim() || null,
    }),
  });
}

export function fetchSettings() {
  return apiJson<SettingsPayload>("/api/settings");
}

export function confirmSourceProfileSample(payload: {
  sourceKey: string;
  note: string;
}) {
  return apiJson<SettingsPayload>("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: "mason",
      changes: [
        {
          domain: "sources",
          setting_key: `sources.${payload.sourceKey}.profile_confirmation_status`,
          value: "owner_confirmed_header_sample",
          note: payload.note.trim(),
        },
      ],
    }),
  });
}

export function fetchArtifacts() {
  return apiJson<{ artifacts: Artifact[] }>("/api/artifacts");
}

export function runReports() {
  return apiJson<ArtifactActionResponse>("/api/reports/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "mason" }),
  });
}

export function draftMonthlyClose() {
  return apiJson<ArtifactActionResponse>("/api/monthly-close/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "mason" }),
  });
}

export function finalizeMonthlyClose() {
  return apiJson<ArtifactActionResponse>("/api/monthly-close/finalize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "mason" }),
  });
}

export function createAdvisorExport() {
  return apiJson<ArtifactActionResponse>("/api/exports/advisor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: "mason" }),
  });
}
