import type {
  Artifact,
  ArtifactActionResponse,
  ActorContext,
  ActorsPayload,
  Category,
  DecisionEventResponse,
  EffectivePermission,
  InboxScan,
  ImportBatch,
  OperatorSummary,
  PermissionPreviewRequest,
  PermissionPreviewResponse,
  SettingsPayload,
  Transaction,
  TransactionDetail,
  ValidationFinding,
} from "./types";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let message = `Request failed: ${path}`;
    let code: string | undefined;
    try {
      const errorBody = await response.json();
      const detail = isRecord(errorBody) ? errorBody.detail : null;
      if (isRecord(detail)) {
        if (typeof detail.message === "string") {
          message = detail.message;
        }
        if (typeof detail.code === "string") {
          code = detail.code;
        }
      } else if (typeof detail === "string") {
        message = detail;
      }
    } catch {
      // Keep the fallback message when the server does not return JSON.
    }
    throw new ApiError(message, response.status, code);
  }
  return response.json() as Promise<T>;
}

export function formatApiError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.code ? `${fallback}: ${error.message} (${error.code})` : `${fallback}: ${error.message}`;
  }
  if (error instanceof Error && error.message) {
    return `${fallback}: ${error.message}`;
  }
  return fallback;
}

function actorContextHeader(actorContext?: ActorContext): HeadersInit | undefined {
  if (!actorContext) {
    return undefined;
  }
  return { "X-Actor-Context": JSON.stringify(actorContext) };
}

export function fetchEffectivePermission(payload: {
  actionKey: string;
  dataScopeKey: string;
  actor?: string;
  actorContext?: ActorContext;
}) {
  const params = new URLSearchParams({
    action_key: payload.actionKey,
    data_scope_key: payload.dataScopeKey,
  });
  if (payload.actor) {
    params.set("actor", payload.actor);
  }
  return apiJson<EffectivePermission>(`/api/permissions/effective?${params.toString()}`, {
    headers: actorContextHeader(payload.actorContext),
  });
}

export function previewPermission(payload: PermissionPreviewRequest) {
  return apiJson<PermissionPreviewResponse>("/api/permissions/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      persona_key: payload.persona_key,
      action_key: payload.action_key,
      data_scope_key: payload.data_scope_key,
      scope_selector: payload.scope_selector ?? null,
    }),
  });
}

export function fetchOperatorSummary() {
  return apiJson<OperatorSummary>("/api/operator-summary");
}

export function fetchActors() {
  return apiJson<ActorsPayload>("/api/actors");
}

export function scanInbox() {
  return apiJson<InboxScan>("/api/inbox/scan");
}

export function uploadSourceFile(payload: { file: File; sourceKey: string }) {
  const body = new FormData();
  body.append("file", payload.file);
  body.append("source_key", payload.sourceKey);
  return apiJson<InboxScan>("/api/uploads", {
    method: "POST",
    body,
  });
}

export function validateImportBatch(batchId: string) {
  return apiJson<ImportBatch & { findings: ValidationFinding[] }>(`/api/import-batches/${batchId}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
}

export function acceptImportBatch(batchId: string) {
  return apiJson<ImportBatch>(`/api/import-batches/${batchId}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ acknowledge_warnings: false }),
  });
}

export function voidImportBatch(payload: {
  batchId: string;
  reason: string;
  destroyFiles: boolean;
  actor: string;
  actorContext?: ActorContext;
}) {
  return apiJson<{ import_batch: ImportBatch }>(`/api/import-batches/${payload.batchId}/void`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      reason: payload.reason,
      destroy_files: payload.destroyFiles,
    }),
  });
}

export function fetchValidationFindings() {
  return apiJson<{ findings: ValidationFinding[] }>("/api/validation-findings");
}

export function resolveValidationFinding(payload: {
  findingId: string;
  note: string;
  actor: string;
  actorContext?: ActorContext;
}) {
  return apiJson<{ finding: ValidationFinding; event?: unknown }>(`/api/validation-findings/${payload.findingId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      note: payload.note.trim(),
    }),
  });
}

export function fetchTransactions() {
  return apiJson<{ transactions: Transaction[] }>("/api/transactions");
}

export function fetchTransactionDetail(transactionId: string) {
  return apiJson<{ transaction: TransactionDetail }>(`/api/transactions/${transactionId}`);
}

export function fetchCategories() {
  return apiJson<{ categories: Category[] }>("/api/categories");
}

export function createCategory(payload: {
  displayName: string;
  aliases?: string[];
  note: string;
  actor: string;
}) {
  return apiJson<{ category: Category }>("/api/categories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      display_name: payload.displayName.trim(),
      aliases: payload.aliases ?? [],
      actor: payload.actor,
      note: payload.note.trim(),
    }),
  });
}

export function saveCategoryDecision(payload: {
  transactionId: string;
  approvedCategoryKey: string;
  actor: string;
  actorContext?: ActorContext;
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
      proposed_value: payload.approvedCategoryKey,
      approved_value: payload.approvedCategoryKey,
      actor: payload.actor,
      actor_context: payload.actorContext,
      suggestion_source: "owner",
      explicit_user_action: true,
      notes: payload.notes?.trim() || null,
    }),
  });
}

export function saveReviewStatusDecision(payload: {
  transactionId: string;
  approvedStatus: "reviewed";
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<DecisionEventResponse>("/api/decision-events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_type: "canonical_transaction",
      target_id: payload.transactionId,
      decision_type: "review_status_change",
      field_name: "review_status",
      proposed_value: payload.approvedStatus,
      approved_value: payload.approvedStatus,
      actor: payload.actor,
      actor_context: payload.actorContext,
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
  actor: string;
  actorContext?: ActorContext;
}) {
  return apiJson<SettingsPayload>("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
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

export function saveSettingChange(payload: {
  domain: string;
  settingKey: string;
  value: unknown;
  actor: string;
  actorContext?: ActorContext;
  note?: string;
}) {
  return apiJson<SettingsPayload>("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      changes: [
        {
          domain: payload.domain,
          setting_key: payload.settingKey,
          value: payload.value,
          note: payload.note?.trim() || null,
        },
      ],
    }),
  });
}

export function fetchArtifacts() {
  return apiJson<{ artifacts: Artifact[] }>("/api/artifacts");
}

export function runReports(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<ArtifactActionResponse>("/api/reports/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: payload.actor, actor_context: payload.actorContext }),
  });
}

export function draftMonthlyClose(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<ArtifactActionResponse>("/api/monthly-close/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: payload.actor, actor_context: payload.actorContext }),
  });
}

export function finalizeMonthlyClose(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<ArtifactActionResponse>("/api/monthly-close/finalize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: payload.actor, actor_context: payload.actorContext }),
  });
}

export function createAdvisorExport(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<ArtifactActionResponse>("/api/exports/advisor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: payload.actor, actor_context: payload.actorContext }),
  });
}
