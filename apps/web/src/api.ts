import type {
  Artifact,
  ArtifactActionResponse,
  ActorContext,
  ActorsPayload,
  ApprovalRequest,
  ApprovalRequestsPayload,
  AuthStatus,
  Category,
  DecisionEventResponse,
  EffectivePermission,
  ElevatedContext,
  ElevatedModeStatus,
  FinancialGoal,
  FundsSummary,
  InboxScan,
  ImportBatch,
  NetWorthSnapshot,
  NetWorthSummary,
  OperatorSummary,
  PermissionPreviewRequest,
  PermissionPreviewResponse,
  SettingsPayload,
  Suggestion,
  SuggestionsPayload,
  Transaction,
  TransactionAllocationsPayload,
  TransactionDetail,
  ValidationFinding,
} from "./types";

const ELEVATED_SESSION_STORAGE_KEY = "family-finance-os.elevatedSessionId";

let elevatedSessionId: string | null = null;

export function getElevatedSessionId(): string | null {
  return elevatedSessionId;
}

export function setElevatedSessionId(sessionId: string | null) {
  elevatedSessionId = sessionId;
  if (typeof window !== "undefined" && window.sessionStorage) {
    if (sessionId) {
      window.sessionStorage.setItem(ELEVATED_SESSION_STORAGE_KEY, sessionId);
    } else {
      window.sessionStorage.removeItem(ELEVATED_SESSION_STORAGE_KEY);
    }
  }
}

export function readStoredElevatedSessionId(): string | null {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return null;
  }
  return window.sessionStorage.getItem(ELEVATED_SESSION_STORAGE_KEY);
}

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

function withElevatedSessionHeaders(init?: RequestInit): RequestInit {
  if (!elevatedSessionId) {
    return init ?? {};
  }
  const headers = new Headers(init?.headers);
  headers.set("X-Elevated-Session-Id", elevatedSessionId);
  return { ...init, headers };
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, withElevatedSessionHeaders(init));
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
      } else if (Array.isArray(detail)) {
        message = detail
          .map((entry) => {
            if (!isRecord(entry)) {
              return String(entry);
            }
            const loc = Array.isArray(entry.loc) ? entry.loc.join(".") : "field";
            return `${loc}: ${typeof entry.msg === "string" ? entry.msg : "invalid"}`;
          })
          .join("; ");
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

export function fetchAuthStatus() {
  return apiJson<AuthStatus>("/api/auth/status");
}

export function loginOwner(payload: { username: string; passphrase: string; totpCode: string }) {
  const { username, passphrase, totpCode } = payload;
  return apiJson<AuthStatus>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: username.trim(),
      passphrase,
      totp_code: totpCode.trim(),
    }),
  });
}

export function recoveryLoginOwner(payload: { username: string; recoveryCode: string }) {
  return apiJson<AuthStatus>("/api/auth/recovery-login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: payload.username.trim(),
      recovery_code: payload.recoveryCode.trim(),
    }),
  });
}

export function enrollOwner(payload: {
  username: string;
  displayName: string;
  passphrase: string;
  totpConfirmCode: string;
  recoveryAcknowledged: boolean;
}) {
  const { username, displayName, passphrase, totpConfirmCode, recoveryAcknowledged } = payload;
  return apiJson<
    AuthStatus & {
      status?: string;
      totp_secret?: string;
      otpauth_uri?: string;
      recovery_codes?: string[];
    }
  >("/api/auth/enroll-owner", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: username.trim(),
      display_name: displayName.trim(),
      passphrase,
      totp_confirm_code: totpConfirmCode.trim(),
      recovery_acknowledged: recoveryAcknowledged,
    }),
  });
}

export function createDevBypassSession() {
  return apiJson<AuthStatus>("/api/auth/dev-bypass", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: "administrator" }),
  });
}

export function fetchFundsSummary(month?: string) {
  const params = new URLSearchParams();
  if (month) {
    params.set("month", month);
  }
  const query = params.toString();
  return apiJson<FundsSummary>(`/api/funds/summary${query ? `?${query}` : ""}`);
}

export function fetchNetWorthSummary(payload?: { includeEstimates?: boolean }) {
  const params = new URLSearchParams();
  if (payload?.includeEstimates) {
    params.set("include_estimates", "true");
  }
  const query = params.toString();
  return apiJson<NetWorthSummary>(`/api/net-worth/summary${query ? `?${query}` : ""}`);
}

export function createNetWorthSnapshot(payload: {
  snapshotDate: string;
  assetOrLiability: string;
  accountName: string;
  institution?: string;
  category: string;
  subcategory?: string;
  balance: string;
  valuationMethod: string;
  confidence?: string;
  sourceNotes?: string;
  actor: string;
  actorContext?: ActorContext;
}) {
  return apiJson<{ snapshot: NetWorthSnapshot }>("/api/net-worth/snapshots", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      snapshot_date: payload.snapshotDate,
      asset_or_liability: payload.assetOrLiability,
      account_name: payload.accountName.trim(),
      institution: payload.institution?.trim() || null,
      category: payload.category.trim(),
      subcategory: payload.subcategory?.trim() || null,
      balance: payload.balance,
      valuation_method: payload.valuationMethod,
      confidence: payload.confidence?.trim() || null,
      source_notes: payload.sourceNotes?.trim() || null,
      actor: payload.actor,
      actor_context: payload.actorContext,
      note: "Create manual net worth snapshot from Settings.",
    }),
  });
}

export function createFinancialGoal(payload: {
  name: string;
  goalType: string;
  targetAmount: string;
  targetDate?: string;
  linkedFundPoolId?: string;
  reservedBalance: string;
  actor: string;
  actorContext?: ActorContext;
}) {
  return apiJson<{ goal: FinancialGoal }>("/api/financial-goals", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name.trim(),
      goal_type: payload.goalType,
      target_amount: payload.targetAmount,
      target_date: payload.targetDate?.trim() || null,
      linked_fund_pool_id: payload.linkedFundPoolId || null,
      reserved_balance: payload.reservedBalance,
      actor: payload.actor,
      actor_context: payload.actorContext,
      note: "Create financial goal from Funds screen.",
    }),
  });
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

export function fetchTransactionAllocations(transactionId: string) {
  return apiJson<TransactionAllocationsPayload>(`/api/transactions/${transactionId}/allocations`);
}

export function saveTransactionAllocations(payload: {
  transactionId: string;
  actor: string;
  actorContext?: ActorContext;
  note?: string;
  lines: Array<{
    amount: string;
    category_id: string;
    subcategory?: string | null;
    fund_pool_id?: string | null;
    financial_goal_id?: string | null;
    memo?: string | null;
  }>;
}) {
  return apiJson<TransactionAllocationsPayload>(`/api/transactions/${payload.transactionId}/allocations`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      note: payload.note?.trim() || null,
      lines: payload.lines,
    }),
  });
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

export function finalizeMonthlyClose(payload: {
  actor: string;
  actorContext?: ActorContext;
  overridePurpose?: string;
}) {
  return apiJson<ArtifactActionResponse>("/api/monthly-close/finalize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      override_purpose: payload.overridePurpose,
    }),
  });
}

export function buildAnalystPack(payload: {
  actor: string;
  actorContext?: ActorContext;
  month?: string;
  includeRawTransactions?: boolean;
  includeEstimates?: boolean;
  promptKey?: string;
}) {
  return apiJson<ArtifactActionResponse & { manifest?: Record<string, unknown> }>("/api/analyst-pack/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      month: payload.month,
      include_raw_transactions: payload.includeRawTransactions ?? false,
      include_estimates: payload.includeEstimates ?? false,
      prompt_key: payload.promptKey ?? "monthly_spending_review",
    }),
  });
}

export function fetchDashboardSummary(month?: string) {
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  return apiJson<Record<string, unknown>>(`/api/dashboard/summary${query}`);
}

export function fetchDashboardCashflow(months = 6, month?: string) {
  const params = new URLSearchParams({ months: String(months) });
  if (month) {
    params.set("month", month);
  }
  return apiJson<{ points: Array<{ month: string; net: string; provisional: boolean }> }>(
    `/api/dashboard/cashflow?${params.toString()}`,
  );
}

export function fetchDashboardCategorySpend(month?: string) {
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  return apiJson<{ categories: Array<{ category: string; outflow: string }> }>(
    `/api/dashboard/category-spend${query}`,
  );
}

export function fetchDashboardPoolProgress(month?: string) {
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  return apiJson<{ pools: Array<{ name: string; progress_percent: string; over_target: boolean }> }>(
    `/api/dashboard/pool-progress${query}`,
  );
}

export function fetchDashboardNetWorth(includeEstimates = false) {
  const params = new URLSearchParams();
  if (includeEstimates) {
    params.set("include_estimates", "true");
  }
  return apiJson<Record<string, unknown>>(`/api/dashboard/net-worth?${params.toString()}`);
}

export function createAdvisorExport(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<ArtifactActionResponse>("/api/exports/advisor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor: payload.actor, actor_context: payload.actorContext }),
  });
}

export function fetchElevatedModeStatus() {
  return apiJson<ElevatedModeStatus>("/api/elevated-mode/status");
}

export function enterElevatedMode(payload: {
  context: ElevatedContext;
  purposeCode: string;
  note?: string;
  actor: string;
  actorContext?: ActorContext;
  hasUnsavedEdits?: boolean;
}) {
  const params = new URLSearchParams();
  if (payload.hasUnsavedEdits) {
    params.set("has_unsaved_edits", "true");
  }
  const query = params.toString();
  return apiJson<ElevatedModeStatus>(`/api/elevated-mode/enter${query ? `?${query}` : ""}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      context: payload.context,
      purpose_code: payload.purposeCode,
      note: (payload.note ?? "").trim(),
      actor: payload.actor,
      actor_context: payload.actorContext,
    }),
  });
}

export function exitElevatedMode(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<{ active: false }>("/api/elevated-mode/exit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
    }),
  });
}

export function touchElevatedMode(payload: { actor: string; actorContext?: ActorContext }) {
  return apiJson<ElevatedModeStatus>("/api/elevated-mode/touch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
    }),
  });
}

export function fetchSuggestions(payload?: { status?: string; targetId?: string }) {
  const params = new URLSearchParams();
  if (payload?.status) {
    params.set("status", payload.status);
  }
  if (payload?.targetId) {
    params.set("target_id", payload.targetId);
  }
  const query = params.toString();
  return apiJson<SuggestionsPayload>(`/api/suggestions${query ? `?${query}` : ""}`);
}

export function createSuggestion(payload: {
  targetType: string;
  targetId: string;
  actionKey: string;
  decisionType: string;
  fieldName: string;
  proposedValue: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ suggestion: Suggestion }>("/api/suggestions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_type: payload.targetType,
      target_id: payload.targetId,
      action_key: payload.actionKey,
      decision_type: payload.decisionType,
      field_name: payload.fieldName,
      proposed_value: payload.proposedValue,
      actor: payload.actor,
      actor_context: payload.actorContext,
      suggestion_source: "user",
      notes: payload.notes?.trim() || null,
    }),
  });
}

export function dismissSuggestion(payload: {
  suggestionId: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ suggestion: Suggestion }>(`/api/suggestions/${payload.suggestionId}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      notes: payload.notes?.trim() || null,
      explicit_user_action: true,
    }),
  });
}

export function acceptSuggestion(payload: {
  suggestionId: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ suggestion: Suggestion; event?: unknown }>(`/api/suggestions/${payload.suggestionId}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      actor_context: payload.actorContext,
      notes: payload.notes?.trim() || null,
      explicit_user_action: true,
    }),
  });
}

export function convertSuggestionToApproval(payload: {
  suggestionId: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ suggestion: Suggestion; approval_request: ApprovalRequest }>(
    `/api/suggestions/${payload.suggestionId}/convert-to-approval`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: payload.actor,
        actor_context: payload.actorContext,
        notes: payload.notes?.trim() || null,
        explicit_user_action: true,
      }),
    },
  );
}

export function fetchApprovalRequests(payload?: { status?: string; targetId?: string }) {
  const params = new URLSearchParams();
  if (payload?.status) {
    params.set("status", payload.status);
  }
  if (payload?.targetId) {
    params.set("target_id", payload.targetId);
  }
  const query = params.toString();
  return apiJson<ApprovalRequestsPayload>(`/api/approval-requests${query ? `?${query}` : ""}`);
}

export function approveApprovalRequest(payload: {
  approvalRequestId: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ approval_request: ApprovalRequest }>(
    `/api/approval-requests/${payload.approvalRequestId}/approve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: payload.actor,
        actor_context: payload.actorContext,
        notes: payload.notes?.trim() || null,
      }),
    },
  );
}

export function rejectApprovalRequest(payload: {
  approvalRequestId: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ approval_request: ApprovalRequest }>(
    `/api/approval-requests/${payload.approvalRequestId}/reject`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: payload.actor,
        actor_context: payload.actorContext,
        notes: payload.notes?.trim() || null,
      }),
    },
  );
}

export function cancelApprovalRequest(payload: {
  approvalRequestId: string;
  actor: string;
  actorContext?: ActorContext;
  notes?: string;
}) {
  return apiJson<{ approval_request: ApprovalRequest }>(
    `/api/approval-requests/${payload.approvalRequestId}/cancel`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        actor: payload.actor,
        actor_context: payload.actorContext,
        notes: payload.notes?.trim() || null,
      }),
    },
  );
}
