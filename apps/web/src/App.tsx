import { FormEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useTranslation } from "react-i18next";

import {
  acceptImportBatch,
  acceptSuggestion,
  approveApprovalRequest,
  cancelApprovalRequest,
  confirmSourceProfileSample,
  convertSuggestionToApproval,
  createCategory,
  createSuggestion,
  dismissSuggestion,
  enterElevatedMode,
  exitElevatedMode,
  fetchApprovalRequests,
  fetchElevatedModeStatus,
  fetchOperatorSummary,
  createAdvisorExport,
  draftMonthlyClose,
  fetchArtifacts,
  fetchActors,
  fetchCategories,
  fetchEffectivePermission,
  fetchSettings,
  fetchSuggestions,
  fetchTransactionDetail,
  fetchTransactions,
  fetchValidationFindings,
  finalizeMonthlyClose,
  formatApiError,
  previewPermission,
  readStoredElevatedSessionId,
  rejectApprovalRequest,
  resolveValidationFinding,
  runReports,
  saveCategoryDecision,
  saveReviewStatusDecision,
  saveSettingChange,
  scanInbox,
  setElevatedSessionId,
  touchElevatedMode,
  uploadSourceFile,
  validateImportBatch,
  voidImportBatch,
} from "./api";
import "./i18n";
import {
  defaultUIPermissionMap,
  permissionAllows,
  permissionSuggests,
  permissionSummaryLabel,
  UI_PERMISSION_CHECKS,
  type UIPermissionMap,
} from "./permissions";
import type {
  Artifact,
  ActorContext,
  ActorsPayload,
  ApprovalRequest,
  Category,
  EffectivePermission,
  ElevatedContext,
  ElevatedModeStatus,
  InboxScan,
  ImportBatch,
  OperatorSummary,
  SettingsPayload,
  SourceProfile,
  Suggestion,
  Transaction,
  TransactionDetail,
  ValidationFinding,
  RuntimeStatus,
} from "./types";
import "./styles.css";

type ScreenKey = "home" | "sources" | "validation" | "review" | "transactions" | "reports" | "settings";
type SettingRow = SettingsPayload["settings"][number];

const screens: Array<{ key: ScreenKey; labelKey: string }> = [
  { key: "home", labelKey: "nav.home" },
  { key: "sources", labelKey: "nav.sources" },
  { key: "validation", labelKey: "nav.validation" },
  { key: "review", labelKey: "nav.review" },
  { key: "transactions", labelKey: "nav.transactions" },
  { key: "reports", labelKey: "nav.reports" },
  { key: "settings", labelKey: "nav.settings" },
];

const OTHER_LIST_VALUE = "__other__";
const OTHER_LIST_LABEL = "Other";

const emptySummary: OperatorSummary = {
  runtime: {
    app: "Family Finance OS",
    version: "0.3.0",
    local_only: true,
    bind_host: "127.0.0.1",
    app_env: "personal",
    app_env_label: "Personal data",
    dataset_kind: "personal",
    dev_mode: false,
    qa_controls_enabled: false,
    data_root: { path: "DATA_ROOT", exists: false },
  },
  latest_import: {
    id: null,
    status: "none",
    validation_status: "none",
    source_key: null,
    row_count: 0,
  },
  sources: {
    required_count: 0,
    imported_source_keys: [],
    missing_required_count: 0,
    profiles: [],
  },
  validation: {
    total_open: 0,
    open_blocking: 0,
    open_warning: 0,
    open_info: 0,
  },
  review: {
    total_transactions: 0,
    unreviewed: 0,
    reviewed: 0,
    blocked: 0,
  },
  monthly_close: {
    status: "not_started",
    ready_for_draft: false,
    ready_for_final: false,
    blockers: [],
  },
  artifacts: {
    generated_count: 0,
    status: "none",
  },
  next_action: {
    code: "loading",
    label: "Load local operating state",
  },
};

function uniqueExistingListValues(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const trimmed = value?.trim();
    if (!trimmed || trimmed.toLowerCase() === OTHER_LIST_LABEL.toLowerCase()) {
      continue;
    }
    const key = trimmed.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    result.push(trimmed);
  }
  return result.sort((left, right) => left.localeCompare(right));
}

function settingValue(settings: SettingsPayload | undefined, domain: string, settingKey: string, fallback: string) {
  const setting = settings?.settings.find((item) => item.domain === domain && item.setting_key === settingKey);
  return typeof setting?.value === "string" && setting.value.trim() ? setting.value : fallback;
}

function settingBoolean(settings: SettingsPayload | undefined, domain: string, settingKey: string, fallback = false) {
  const setting = settings?.settings.find((item) => item.domain === domain && item.setting_key === settingKey);
  if (typeof setting?.value === "boolean") {
    return setting.value;
  }
  if (typeof setting?.value === "string") {
    return setting.value.toLowerCase() === "true";
  }
  return fallback;
}

const ELEVATED_PURPOSE_LABELS: Record<string, string> = {
  user_group_permission_management: "User, group, or permission management",
  source_or_system_settings: "Source or system settings",
  maintenance_health_review: "Maintenance or health review",
  runtime_troubleshooting: "Runtime troubleshooting",
  approval_rule_change: "Approval-rule change",
  governance_setting_change: "Governance setting change",
  threshold_risk_rule_review: "Threshold or risk-rule review",
  monthly_close_governance_review: "Monthly-close governance review",
};

type ControlPlaneMode = "operator" | ElevatedContext;

const CONTROL_PLANE_MODE_LABELS: Record<ControlPlaneMode, string> = {
  operator: "Operator Mode",
  system_administration: "Administrator Mode",
  financial_governance: "Financial Governor Mode",
};

const FALLBACK_PURPOSE_CODES_REQUIRING_NOTE = new Set(["approval_rule_change"]);

function purposeRequiresNote(purposeCode: string, status?: ElevatedModeStatus): boolean {
  const configured = status?.purpose_requires_note;
  if (configured && configured.length > 0) {
    return configured.includes(purposeCode);
  }
  return FALLBACK_PURPOSE_CODES_REQUIRING_NOTE.has(purposeCode);
}

function controlPlaneModeFromStatus(active: boolean, context?: ElevatedContext): ControlPlaneMode {
  if (active && context) {
    return context;
  }
  return "operator";
}

function elevatedPurposeLabel(code: string) {
  return ELEVATED_PURPOSE_LABELS[code] ?? formatStatus(code);
}

function formatCountdown(expiresAt: string | undefined, nowMs: number) {
  if (!expiresAt) {
    return "—";
  }
  const remainingMs = new Date(expiresAt).getTime() - nowMs;
  if (remainingMs <= 0) {
    return "Expired";
  }
  const totalSeconds = Math.floor(remainingMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

const ACTIVE_ACTOR_STORAGE_KEY = "family-finance-os.activeActorKey";
const ACTIVE_PERSONA_STORAGE_KEY = "family-finance-os.activePersonaKey";

function readLocalStorage(key: string, fallback: string) {
  if (typeof window === "undefined" || !window.localStorage) {
    return fallback;
  }
  return window.localStorage.getItem(key) || fallback;
}

function writeLocalStorage(key: string, value: string) {
  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.setItem(key, value);
  }
}

function actorContextFromSelection(
  actors: ActorsPayload | undefined,
  actorKey: string,
  personaKey: string,
): ActorContext {
  const actor = actors?.human_actors.find((item) => item.actor_key === actorKey) ?? actors?.human_actors[0];
  const persona = actors?.selectable_personas.find((item) => item.persona_key === personaKey) ?? actors?.selectable_personas[0];
  return {
    actor_key: actor?.actor_key ?? "owner",
    actor_type: "human",
    display_name: actor?.display_name ?? "Owner",
    persona_key: persona?.persona_key ?? "finance_manager",
    persona_label: persona?.persona_label ?? "Finance Manager",
    group_keys: persona?.group_keys ?? actor?.group_keys ?? ["finance_manager"],
    source: "local_selector",
  };
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

async function fetchUIPermissions(actor: string, actorContext: ActorContext): Promise<UIPermissionMap> {
  const entries = await Promise.all(
    UI_PERMISSION_CHECKS.map(async (check) => {
      const permission = await fetchEffectivePermission({
        actionKey: check.action_key,
        dataScopeKey: check.data_scope_key,
        actor,
        actorContext,
      });
      return [check.id, permission] as const;
    }),
  );
  return Object.fromEntries(entries);
}

function useUIPermissions(actor: string, actorContext: ActorContext) {
  return useQuery({
    queryKey: ["permissions-effective", actor, actorContext.persona_key, actorContext.group_keys.join(",")],
    queryFn: () => fetchUIPermissions(actor, actorContext),
  });
}

function useElevatedMode(actor: string, actorContext: ActorContext) {
  const queryClient = useQueryClient();
  const [countdownNow, setCountdownNow] = useState(() => Date.now());

  useEffect(() => {
    const storedSessionId = readStoredElevatedSessionId();
    if (storedSessionId) {
      setElevatedSessionId(storedSessionId);
    }
  }, []);

  const statusQuery = useQuery({
    queryKey: ["elevated-mode-status"],
    queryFn: fetchElevatedModeStatus,
    refetchInterval: (query) => (query.state.data?.active ? 30_000 : false),
  });

  const activeStatus = statusQuery.data?.active ? statusQuery.data : null;

  useEffect(() => {
    if (activeStatus?.session_id) {
      setElevatedSessionId(activeStatus.session_id);
      return;
    }
    setElevatedSessionId(null);
  }, [activeStatus?.session_id]);

  useEffect(() => {
    if (!activeStatus?.expires_at) {
      return;
    }
    const timer = window.setInterval(() => setCountdownNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [activeStatus?.expires_at]);

  useEffect(() => {
    if (!activeStatus?.session_id) {
      return;
    }
    const touchTimer = window.setInterval(() => {
      void touchElevatedMode({ actor, actorContext })
        .then((body) => {
          queryClient.setQueryData(["elevated-mode-status"], body);
        })
        .catch(() => {
          void queryClient.invalidateQueries({ queryKey: ["elevated-mode-status"] });
        });
    }, 5 * 60 * 1000);
    return () => window.clearInterval(touchTimer);
  }, [activeStatus?.session_id, actor, actorContext, queryClient]);

  const enterMutation = useMutation({
    mutationFn: enterElevatedMode,
    onSuccess: (body, _variables, _context) => {
      if (body.session_id) {
        setElevatedSessionId(body.session_id);
      }
      const prior = queryClient.getQueryData<ElevatedModeStatus>(["elevated-mode-status"]);
      queryClient.setQueryData(["elevated-mode-status"], {
        ...body,
        purpose_codes: body.purpose_codes ?? prior?.purpose_codes,
        purpose_requires_note: body.purpose_requires_note ?? prior?.purpose_requires_note,
      });
    },
  });

  const exitMutation = useMutation({
    mutationFn: exitElevatedMode,
    onSuccess: () => {
      setElevatedSessionId(null);
      queryClient.setQueryData(["elevated-mode-status"], {
        active: false,
        purpose_codes: statusQuery.data?.purpose_codes,
        purpose_requires_note: statusQuery.data?.purpose_requires_note,
      });
      void queryClient.invalidateQueries({ queryKey: ["elevated-mode-status"] });
    },
  });

  return {
    status: statusQuery.data,
    active: Boolean(activeStatus),
    countdown: formatCountdown(activeStatus?.expires_at, countdownNow),
    enterMutation,
    exitMutation,
    isLoading: statusQuery.isLoading,
    isError: statusQuery.isError,
    error: statusQuery.error,
  };
}

export function App() {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <OperatorApp />
    </QueryClientProvider>
  );
}

function OperatorApp() {
  const { t } = useTranslation();
  const [activeScreen, setActiveScreen] = useState<ScreenKey>("home");
  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);
  const [activeActorKey, setActiveActorKey] = useState(() => readLocalStorage(ACTIVE_ACTOR_STORAGE_KEY, "owner"));
  const [activePersonaKey, setActivePersonaKey] = useState(() =>
    readLocalStorage(ACTIVE_PERSONA_STORAGE_KEY, "finance_manager"),
  );

  const summaryQuery = useQuery({ queryKey: ["operator-summary"], queryFn: fetchOperatorSummary });
  const actorsQuery = useQuery({ queryKey: ["actors"], queryFn: fetchActors });
  const inboxQuery = useQuery({ queryKey: ["inbox-scan"], queryFn: scanInbox });
  const findingsQuery = useQuery({ queryKey: ["validation-findings"], queryFn: fetchValidationFindings });
  const transactionsQuery = useQuery({ queryKey: ["transactions"], queryFn: fetchTransactions });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const artifactsQuery = useQuery({ queryKey: ["artifacts"], queryFn: fetchArtifacts });
  const categoriesQuery = useQuery({ queryKey: ["categories"], queryFn: fetchCategories });

  const transactions = transactionsQuery.data?.transactions ?? [];
  useEffect(() => {
    if (!selectedTransactionId && transactions.length > 0) {
      setSelectedTransactionId(transactions[0].id);
    }
  }, [selectedTransactionId, transactions]);

  const transactionDetailQuery = useQuery({
    queryKey: ["transaction", selectedTransactionId],
    queryFn: () => fetchTransactionDetail(selectedTransactionId as string),
    enabled: Boolean(selectedTransactionId),
  });

  const summary = summaryQuery.data ?? emptySummary;
  const actors = actorsQuery.data;
  const findings = findingsQuery.data?.findings ?? [];
  const inbox = inboxQuery.data?.import_batches ?? [];
  const settings = settingsQuery.data;
  const appDisplayName = settingValue(settings, "branding", "branding.app_display_name", summary.runtime.app || t("app.fallbackName"));
  const operatorActorContext = actorContextFromSelection(actors, activeActorKey, activePersonaKey);
  const operatorActor = operatorActorContext.actor_key;
  const permissionsQuery = useUIPermissions(operatorActor, operatorActorContext);
  const permissions = permissionsQuery.data ?? defaultUIPermissionMap();
  const elevatedMode = useElevatedMode(operatorActor, operatorActorContext);
  const elevatedModeActive = elevatedMode.active;
  const categories = categoriesQuery.data?.categories ?? [];
  const sourceProfileKey = summary.sources.profiles.map((profile) => profile.source_key).join("|") || "no-source-profiles";
  const selectedTransaction =
    transactionDetailQuery.data?.transaction ??
    transactions.find((transaction) => transaction.id === selectedTransactionId) ??
    null;

  return (
    <div className="app-shell">
      {summary.runtime.app_env === "qa" ? (
        <div className="qa-banner" role="status">
          QA synthetic demo - not real financial data
        </div>
      ) : null}
      <Header
        summary={summary}
        appDisplayName={appDisplayName}
        actors={actors}
        activeActorKey={operatorActorContext.actor_key}
        activePersonaKey={operatorActorContext.persona_key ?? "finance_manager"}
        onActorChange={(value) => {
          setActiveActorKey(value);
          writeLocalStorage(ACTIVE_ACTOR_STORAGE_KEY, value);
        }}
        onPersonaChange={(value) => {
          setActivePersonaKey(value);
          writeLocalStorage(ACTIVE_PERSONA_STORAGE_KEY, value);
        }}
        elevation={{
          status: elevatedMode.status,
          active: elevatedModeActive,
          countdown: elevatedMode.countdown,
          operatorActor,
          operatorActorContext,
          enterMutation: elevatedMode.enterMutation,
          exitMutation: elevatedMode.exitMutation,
          isLoading: elevatedMode.isLoading,
          isError: elevatedMode.isError,
          error: elevatedMode.error,
        }}
      />

      <div className="workspace">
        <nav className="sidebar" aria-label="Primary">
          {screens.map((screen) => (
            <a
              key={screen.key}
              href={`#${screen.key}`}
              aria-current={activeScreen === screen.key ? "page" : undefined}
              onClick={(event) => {
                event.preventDefault();
                setActiveScreen(screen.key);
              }}
            >
              {t(screen.labelKey)}
            </a>
          ))}
        </nav>

        <main className="content">
          {activeScreen === "home" ? <HomeScreen summary={summary} /> : null}
          {activeScreen === "sources" ? (
            <SourcesScreen
              key={sourceProfileKey}
              profiles={summary.sources.profiles}
              inbox={inbox}
              operatorActor={operatorActor}
              operatorActorContext={operatorActorContext}
              canRunImports={permissionAllows(permissions.imports) && !elevatedModeActive}
              elevatedModeActive={elevatedModeActive}
            />
          ) : null}
          {activeScreen === "validation" ? (
            <ValidationScreen
              findings={findings}
              operatorActor={operatorActor}
              operatorActorContext={operatorActorContext}
              elevatedModeActive={elevatedModeActive}
            />
          ) : null}
          {activeScreen === "review" ? (
            <ReviewScreen
              transactions={transactions}
              selectedTransaction={selectedTransaction}
              selectedTransactionId={selectedTransactionId}
              categories={categories}
              operatorActor={operatorActor}
              operatorActorContext={operatorActorContext}
              canSaveReview={permissionAllows(permissions.review) && !elevatedModeActive}
              reviewSuggestionAllowed={permissionSuggests(permissions.review)}
              elevatedModeActive={elevatedModeActive}
              approvalModeEnabled={settingBoolean(settings, "approval", "approval.approval_mode_enabled")}
              onSelectTransaction={setSelectedTransactionId}
            />
          ) : null}
          {activeScreen === "transactions" ? (
            <TransactionsScreen
              transactions={transactions}
              selectedTransaction={selectedTransaction}
              selectedTransactionId={selectedTransactionId}
              onSelectTransaction={setSelectedTransactionId}
            />
          ) : null}
          {activeScreen === "reports" ? (
            <ReportsScreen
              summary={summary}
              artifacts={artifactsQuery.data?.artifacts ?? []}
              operatorActor={operatorActor}
              operatorActorContext={operatorActorContext}
              canRunReports={permissionAllows(permissions.reports) && !elevatedModeActive}
              canRunMonthlyClose={permissionAllows(permissions.monthlyClose) && !elevatedModeActive}
              canCreateExports={permissionAllows(permissions.exports) && !elevatedModeActive}
              elevatedModeActive={elevatedModeActive}
            />
          ) : null}
          {activeScreen === "settings" ? (
            <SettingsScreen
              settings={settings}
              runtime={summary.runtime}
              profiles={summary.sources.profiles}
              operatorActor={operatorActor}
              operatorActorContext={operatorActorContext}
              canSaveSettings={permissionAllows(permissions.settings)}
              approvalModeEnabled={settingBoolean(settings, "approval", "approval.approval_mode_enabled")}
              canManageApprovals={permissionAllows(permissions.review)}
              qaControlsEnabled={summary.runtime.qa_controls_enabled}
              actors={actors}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}

function Header({
  summary,
  appDisplayName,
  actors,
  activeActorKey,
  activePersonaKey,
  onActorChange,
  onPersonaChange,
  elevation,
}: {
  summary: OperatorSummary;
  appDisplayName: string;
  actors?: ActorsPayload;
  activeActorKey: string;
  activePersonaKey: string;
  onActorChange: (value: string) => void;
  onPersonaChange: (value: string) => void;
  elevation: {
    status?: ElevatedModeStatus;
    active: boolean;
    countdown: string;
    operatorActor: string;
    operatorActorContext: ActorContext;
    enterMutation: ReturnType<typeof useMutation<ElevatedModeStatus, Error, Parameters<typeof enterElevatedMode>[0]>>;
    exitMutation: ReturnType<typeof useMutation<{ active: false }, Error, Parameters<typeof exitElevatedMode>[0]>>;
    isLoading: boolean;
    isError: boolean;
    error: unknown;
  };
}) {
  const { t } = useTranslation();
  return (
    <header className="topbar">
      <div>
        <p className="product-label">{t("app.productLabel")}</p>
        <h1>{appDisplayName}</h1>
      </div>
      <div className="actor-controls" aria-label="Active local actor">
        <ElevationControls {...elevation} />
        <label>
          Actor
          <select value={activeActorKey} onChange={(event) => onActorChange(event.target.value)}>
            {(actors?.human_actors ?? [{ actor_key: "owner", display_name: "Owner" }]).map((actor) => (
              <option key={actor.actor_key} value={actor.actor_key}>
                {actor.display_name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Persona
          <select value={activePersonaKey} onChange={(event) => onPersonaChange(event.target.value)}>
            {(actors?.selectable_personas ?? [{ persona_key: "finance_manager", persona_label: "Finance Manager" }]).map(
              (persona) => (
                <option key={persona.persona_key} value={persona.persona_key}>
                  {persona.persona_label}
                </option>
              ),
            )}
          </select>
        </label>
      </div>
      <div className="status-strip" aria-label="Runtime status">
        {elevation.active ? (
          <span className="warn">
            {CONTROL_PLANE_MODE_LABELS[controlPlaneModeFromStatus(true, elevation.status?.context)]} ·{" "}
            {elevation.countdown}
          </span>
        ) : null}
        <span className={summary.runtime.app_env === "qa" ? "danger" : "ok"}>{summary.runtime.app_env_label}</span>
        <span>{summary.runtime.dataset_kind}</span>
        <span className={summary.runtime.local_only ? "ok" : "danger"}>{t("runtime.localBrowserMode")}</span>
        <span>{summary.runtime.bind_host}</span>
        <span>{summary.runtime.data_root.exists ? t("runtime.dataRootMounted") : t("runtime.dataRootUnavailable")}</span>
        <span>
          {t("runtime.close")}: {formatStatus(summary.monthly_close.status)}
        </span>
      </div>
    </header>
  );
}

function ElevationControls({
  status,
  active,
  countdown,
  operatorActor,
  operatorActorContext,
  enterMutation,
  exitMutation,
  isLoading,
  isError,
  error,
}: {
  status?: ElevatedModeStatus;
  active: boolean;
  countdown: string;
  operatorActor: string;
  operatorActorContext: ActorContext;
  enterMutation: ReturnType<typeof useMutation<ElevatedModeStatus, Error, Parameters<typeof enterElevatedMode>[0]>>;
  exitMutation: ReturnType<typeof useMutation<{ active: false }, Error, Parameters<typeof exitElevatedMode>[0]>>;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
}) {
  const displayMode = controlPlaneModeFromStatus(active, status?.context);
  const [selectValue, setSelectValue] = useState<ControlPlaneMode>(displayMode);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [pendingContext, setPendingContext] = useState<ElevatedContext | null>(null);
  const [purposeCode, setPurposeCode] = useState("");
  const [note, setNote] = useState("");
  const [formStatus, setFormStatus] = useState<string | null>(null);
  const noteRequired = purposeCode ? purposeRequiresNote(purposeCode, status) : false;
  const purposeCodes = pendingContext ? (status?.purpose_codes?.[pendingContext] ?? []) : [];
  const confirmDisabled =
    !pendingContext ||
    !purposeCode.trim() ||
    (noteRequired && !note.trim()) ||
    enterMutation.isPending ||
    exitMutation.isPending;

  useEffect(() => {
    setSelectValue(displayMode);
  }, [displayMode]);

  useEffect(() => {
    if (!lightboxOpen) {
      return;
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeLightbox();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [lightboxOpen, displayMode]);

  function openLightbox(context: ElevatedContext) {
    setPendingContext(context);
    setPurposeCode("");
    setNote("");
    setFormStatus(null);
    setLightboxOpen(true);
  }

  function closeLightbox() {
    setLightboxOpen(false);
    setPendingContext(null);
    setPurposeCode("");
    setNote("");
    setSelectValue(displayMode);
  }

  function handleModeChange(nextMode: ControlPlaneMode) {
    setSelectValue(nextMode);
    if (nextMode === displayMode && nextMode !== "operator" && active) {
      openLightbox(nextMode);
      return;
    }
    if (nextMode === displayMode) {
      return;
    }
    if (nextMode === "operator") {
      if (!active) {
        return;
      }
      setFormStatus(null);
      exitMutation.mutate(
        { actor: operatorActor, actorContext: operatorActorContext },
        {
          onError: (exitError) => {
            setFormStatus(formatApiError(exitError, "Elevated mode exit blocked"));
            setSelectValue(displayMode);
          },
        },
      );
      return;
    }
    openLightbox(nextMode);
  }

  async function confirmElevatedEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pendingContext || confirmDisabled) {
      return;
    }
    setFormStatus(null);
    try {
      if (active) {
        await exitMutation.mutateAsync({ actor: operatorActor, actorContext: operatorActorContext });
      }
      await enterMutation.mutateAsync({
        context: pendingContext,
        purposeCode,
        note,
        actor: operatorActor,
        actorContext: operatorActorContext,
      });
      setLightboxOpen(false);
      setPendingContext(null);
      setPurposeCode("");
      setNote("");
    } catch (enterError) {
      setFormStatus(formatApiError(enterError, "Elevated mode entry blocked"));
      setSelectValue(displayMode);
    }
  }

  return (
    <>
      <label className="elevation-mode-control">
        Control plane
        <select
          value={selectValue}
          onChange={(event) => handleModeChange(event.target.value as ControlPlaneMode)}
          aria-label="Control plane mode"
        >
          {(Object.keys(CONTROL_PLANE_MODE_LABELS) as ControlPlaneMode[]).map((mode) => (
            <option key={mode} value={mode}>
              {CONTROL_PLANE_MODE_LABELS[mode]}
            </option>
          ))}
        </select>
      </label>
      {active && status?.context ? (
        <button
          type="button"
          className="link-button elevation-reenter"
          onClick={() => openLightbox(status.context!)}
        >
          Re-enter
        </button>
      ) : null}
      {active ? (
        <span className="elevation-countdown-inline" aria-live="polite">
          {countdown}
        </span>
      ) : null}
      {isError ? (
        <span className="form-status danger-text">{formatApiError(error, "Elevated mode unavailable")}</span>
      ) : null}
      {isLoading ? <span className="muted-text">Loading elevation…</span> : null}
      {formStatus && !lightboxOpen ? (
        <span
          className={
            formStatus.includes("blocked") || formStatus.includes("unavailable")
              ? "form-status danger-text"
              : "form-status ok-text"
          }
        >
          {formStatus}
        </span>
      ) : null}

      {lightboxOpen && pendingContext ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeLightbox();
            }
          }}
        >
          <section
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="elevation-lightbox-title"
          >
            <h3 id="elevation-lightbox-title">Enter {CONTROL_PLANE_MODE_LABELS[pendingContext]}</h3>
            <p className="modal-copy">
              Select a purpose for this elevated session. Routine financial mutations stay read-only while elevated.
            </p>
            <form className="modal-form" onSubmit={confirmElevatedEntry}>
              <label>
                Purpose
                <select
                  value={purposeCode}
                  onChange={(event) => setPurposeCode(event.target.value)}
                  required
                >
                  <option value="">Select purpose…</option>
                  {purposeCodes.map((code) => (
                    <option key={code} value={code}>
                      {elevatedPurposeLabel(code)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {noteRequired ? "Required note" : "Note (optional)"}
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={3}
                  required={noteRequired}
                />
              </label>
              {formStatus ? (
                <p
                  className={
                    formStatus.includes("blocked") || formStatus.includes("unavailable")
                      ? "form-status danger-text"
                      : "form-status ok-text"
                  }
                >
                  {formStatus}
                </p>
              ) : null}
              <div className="button-row">
                <button type="button" onClick={closeLightbox} disabled={enterMutation.isPending || exitMutation.isPending}>
                  Decline
                </button>
                <button type="submit" disabled={confirmDisabled}>
                  Confirm
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}

function PermissionPreviewPanel({ actors }: { actors?: ActorsPayload }) {
  const [expanded, setExpanded] = useState(false);
  const personas = actors?.selectable_personas ?? [
    { persona_key: "finance_manager", persona_label: "Finance Manager", group_keys: ["finance_manager"] },
  ];
  const [previewPersonaKey, setPreviewPersonaKey] = useState(personas[0]?.persona_key ?? "finance_manager");
  const previewQuery = useQuery({
    queryKey: ["permissions-preview", previewPersonaKey],
    enabled: expanded,
    queryFn: async () => {
      const entries = await Promise.all(
        UI_PERMISSION_CHECKS.map(async (check) => {
          const result = await previewPermission({
            persona_key: previewPersonaKey,
            action_key: check.action_key,
            data_scope_key: check.data_scope_key,
          });
          return [check.id, result] as const;
        }),
      );
      return Object.fromEntries(entries) as Record<string, EffectivePermission>;
    },
  });
  const previewResults = previewQuery.data;

  return (
    <details
      className="collapsible-section permission-preview-collapsible"
      onToggle={(event) => setExpanded((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        <span className="product-label">QA permission matrix</span>
        <span className="collapsible-title">Permission preview</span>
      </summary>
      {expanded ? (
        <div className="permission-preview-panel" aria-label="Permission preview">
          <div className="permission-preview-header">
            <label>
              Preview persona
              <select value={previewPersonaKey} onChange={(event) => setPreviewPersonaKey(event.target.value)}>
                {personas.map((persona) => (
                  <option key={persona.persona_key} value={persona.persona_key}>
                    {persona.persona_label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {previewQuery.isLoading ? <p className="empty-state">Loading permission preview…</p> : null}
          {previewQuery.isError ? (
            <p className="form-status danger-text">{formatApiError(previewQuery.error, "Permission preview unavailable")}</p>
          ) : null}
          {previewResults ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Effect</th>
                    <th>Scope access</th>
                  </tr>
                </thead>
                <tbody>
                  {UI_PERMISSION_CHECKS.map((check) => {
                    const result = previewResults[check.id];
                    const tone = result.allowed ? "ok-text" : result.suggestion_allowed ? "warn-text" : "danger-text";
                    return (
                      <tr key={check.id}>
                        <td>{check.label}</td>
                        <td className={tone}>{permissionSummaryLabel(result)}</td>
                        <td>{result.scope_access ? formatStatus(result.scope_access) : "None"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </details>
  );
}

function HomeScreen({ summary }: { summary: OperatorSummary }) {
  return (
    <section className="screen" aria-labelledby="home-heading">
      <div className="screen-heading split-heading">
        <div>
          <p className="product-label">Current operating state</p>
          <h2 id="home-heading">Home</h2>
        </div>
        <div className="next-action">
          <span>Next action</span>
          <strong>{summary.next_action.label}</strong>
        </div>
      </div>

      <div className="metric-grid" aria-label="Operator overview">
        <Metric label="Latest import" value={formatStatus(summary.latest_import.status)} detail={summary.latest_import.source_key ?? "No source loaded"} />
        <Metric label="Open blockers" value={summary.validation.open_blocking} detail={`${summary.validation.open_warning} warning(s)`} tone={summary.validation.open_blocking ? "danger" : "ok"} />
        <Metric label="Review queue" value={summary.review.unreviewed} detail={`${summary.review.total_transactions} ledger transaction(s)`} />
        <Metric label="Required sources" value={`${summary.sources.required_count - summary.sources.missing_required_count}/${summary.sources.required_count}`} detail={`${summary.sources.missing_required_count} missing`} tone={summary.sources.missing_required_count ? "warn" : "ok"} />
        <Metric label="Monthly close" value={summary.monthly_close.ready_for_final ? "Ready" : "Not ready"} detail={summary.monthly_close.ready_for_draft ? "Draft allowed" : "Draft blocked"} tone={summary.monthly_close.ready_for_final ? "ok" : "warn"} />
        <Metric label="Data root" value={summary.runtime.data_root.exists ? "Available" : "Missing"} detail={summary.runtime.data_root.path} tone={summary.runtime.data_root.exists ? "ok" : "danger"} />
      </div>

      <section className="work-panel" aria-label="Closed-loop checkpoint">
        <h3>Closed-loop checkpoint</h3>
        <div className="step-grid">
          {[
            ["Source", summary.latest_import.status !== "none"],
            ["Validation", summary.validation.open_blocking === 0],
            ["Review", summary.review.unreviewed === 0 && summary.review.total_transactions > 0],
            ["Reports", Boolean(summary.artifacts?.generated_count)],
            ["Close", summary.monthly_close.ready_for_final],
          ].map(([label, complete]) => (
            <span key={label as string} className={complete ? "step done" : "step"}>
              {label as string}
            </span>
          ))}
        </div>
      </section>
    </section>
  );
}

function SourcesScreen({
  profiles,
  inbox,
  operatorActor,
  operatorActorContext,
  canRunImports,
  elevatedModeActive,
}: {
  profiles: SourceProfile[];
  inbox: ImportBatch[];
  operatorActor: string;
  operatorActorContext: ActorContext;
  canRunImports: boolean;
  elevatedModeActive: boolean;
}) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedUploadSourceKey, setSelectedUploadSourceKey] = useState(profiles[0]?.source_key ?? "");
  const [batchActionStatus, setBatchActionStatus] = useState<string | null>(null);
  const [voidTarget, setVoidTarget] = useState<ImportBatch | null>(null);
  const [voidReason, setVoidReason] = useState("");
  const [destroyStoredFiles, setDestroyStoredFiles] = useState(false);
  const uploadSourceKey = selectedUploadSourceKey || profiles[0]?.source_key || "";

  useEffect(() => {
    if (!selectedUploadSourceKey && profiles[0]) {
      setSelectedUploadSourceKey(profiles[0].source_key);
    }
    if (selectedUploadSourceKey && !profiles.some((profile) => profile.source_key === selectedUploadSourceKey)) {
      setSelectedUploadSourceKey(profiles[0]?.source_key ?? "");
    }
  }, [profiles, selectedUploadSourceKey]);

  function updateCachedBatch(updatedBatch: ImportBatch) {
    queryClient.setQueryData<InboxScan>(["inbox-scan"], (current) => {
      if (!current) {
        return current;
      }
      return {
        import_batches: current.import_batches.map((batch) =>
          batch.id === updatedBatch.id
            ? { ...batch, ...updatedBatch, source_files: updatedBatch.source_files?.length ? updatedBatch.source_files : batch.source_files }
            : batch,
        ),
      };
    });
  }

  function refreshImportState() {
    void queryClient.invalidateQueries({ queryKey: ["inbox-scan"] });
    void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
    void queryClient.invalidateQueries({ queryKey: ["validation-findings"] });
    void queryClient.invalidateQueries({ queryKey: ["transactions"] });
  }

  function refreshAfterBatchAction() {
    void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
    void queryClient.invalidateQueries({ queryKey: ["validation-findings"] });
    void queryClient.invalidateQueries({ queryKey: ["transactions"] });
  }

  const uploadMutation = useMutation({
    mutationFn: uploadSourceFile,
    onSuccess: () => {
      setSelectedFile(null);
      setBatchActionStatus("File uploaded to inbox");
      refreshImportState();
    },
  });
  const validateMutation = useMutation({
    mutationFn: validateImportBatch,
    onSuccess: (body) => {
      updateCachedBatch(body);
      setBatchActionStatus("Batch validation completed");
      refreshAfterBatchAction();
    },
    onError: (error) => setBatchActionStatus(formatApiError(error, "Batch validation blocked")),
  });
  const acceptMutation = useMutation({
    mutationFn: acceptImportBatch,
    onSuccess: (body) => {
      updateCachedBatch(body);
      setBatchActionStatus("Batch accepted");
      refreshAfterBatchAction();
    },
    onError: (error) => setBatchActionStatus(formatApiError(error, "Batch acceptance blocked")),
  });
  const voidMutation = useMutation({
    mutationFn: voidImportBatch,
    onSuccess: (body, variables) => {
      updateCachedBatch(body.import_batch);
      setBatchActionStatus(
        variables.destroyFiles ? "Upload voided and stored files destroyed" : "Upload voided; stored files preserved",
      );
      setVoidTarget(null);
      setVoidReason("");
      setDestroyStoredFiles(false);
      refreshImportState();
    },
    onError: (error) => setBatchActionStatus(formatApiError(error, "Upload void blocked")),
  });

  const blockedBatches = inbox.filter((batch) => batch.status === "blocked" || batch.validation_status === "blocked");
  const batchActionPending = validateMutation.isPending || acceptMutation.isPending || voidMutation.isPending;

  function openVoidDialog(batch: ImportBatch) {
    setVoidTarget(batch);
    setVoidReason("");
    setDestroyStoredFiles(false);
    setBatchActionStatus(null);
  }

  function closeVoidDialog() {
    setVoidTarget(null);
    setVoidReason("");
    setDestroyStoredFiles(false);
  }

  function confirmVoidUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!voidTarget || !voidReason.trim()) {
      return;
    }
    voidMutation.mutate({
      batchId: voidTarget.id,
      reason: voidReason.trim(),
      destroyFiles: destroyStoredFiles,
      actor: operatorActor,
      actorContext: operatorActorContext,
    });
  }

  return (
    <section className="screen" aria-labelledby="sources-heading">
      <div className="screen-heading split-heading">
        <div>
          <p className="product-label">Source files and profiles</p>
          <h2 id="sources-heading">Sources</h2>
        </div>
        <div className="button-row">
          <button type="button" onClick={() => void queryClient.invalidateQueries({ queryKey: ["inbox-scan"] })}>
            Scan inbox
          </button>
        </div>
      </div>

      <section className="work-panel">
        <h3>Source profile templates</h3>
        <div className="source-grid">
          {profiles.map((profile) => (
            <article key={profile.source_key} className="source-card">
              <div>
                <h4>{profile.display_name}</h4>
                <span>{formatStatus(profile.account_type)}</span>
              </div>
              <dl>
                <div>
                  <dt>Template</dt>
                  <dd>{profile.is_template ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Enabled</dt>
                  <dd>{profile.enabled ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Required</dt>
                  <dd>{profile.required ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Freshness</dt>
                  <dd>{profile.freshness_threshold_days} days</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{formatStatus(profile.latest_import_status ?? "none")}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="two-column">
        <div className="work-panel">
          <h3>Import batches</h3>
          {!canRunImports ? (
            <p className="form-status warn-text">
              {elevatedModeActive
                ? "Import mutations are disabled while elevated mode is active."
                : "Current persona cannot run import mutations."}
            </p>
          ) : null}
          {batchActionStatus ? <p className="form-status">{batchActionStatus}</p> : null}
          <DataTable
            data={inbox}
            emptyLabel="No import batches tracked"
            columns={[
              { header: "Batch", cell: ({ row }) => row.original.id.slice(0, 8) },
              { header: "Source", accessorKey: "source_key" },
              { header: "Status", accessorKey: "status" },
              { header: "Validation", accessorKey: "validation_status" },
              { header: "Rows", accessorKey: "row_count" },
              {
                header: "Actions",
                cell: ({ row }) => {
                  const batchClosed = row.original.status === "accepted" || row.original.status === "voided";
                  if (batchClosed) {
                    return <span className="muted-text">{formatStatus(row.original.status)}</span>;
                  }
                  return (
                    <div className="table-actions">
                      <button
                        type="button"
                        className="link-button"
                        disabled={batchActionPending || !canRunImports}
                        onClick={() => validateMutation.mutate(row.original.id)}
                      >
                        Validate batch
                      </button>
                      <button
                        type="button"
                        className="link-button"
                        disabled={batchActionPending || !canRunImports || row.original.validation_status === "pending"}
                        onClick={() => acceptMutation.mutate(row.original.id)}
                      >
                        Accept batch
                      </button>
                      <button
                        type="button"
                        className="link-button danger-link"
                        disabled={batchActionPending || !canRunImports}
                        onClick={() => openVoidDialog(row.original)}
                      >
                        Void upload
                      </button>
                    </div>
                  );
                },
              },
            ]}
          />
        </div>

        <div className="work-panel">
          <h3>Upload</h3>
          <form
            className="upload-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (selectedFile && uploadSourceKey) {
                uploadMutation.mutate({ file: selectedFile, sourceKey: uploadSourceKey });
              }
            }}
          >
            <label>
              Source profile
              <select value={uploadSourceKey} onChange={(event) => setSelectedUploadSourceKey(event.target.value)}>
                {profiles.map((profile) => (
                  <option key={profile.source_key} value={profile.source_key}>
                    {profile.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Source file
              <input type="file" accept=".csv" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
            </label>
            <button type="submit" disabled={!selectedFile || !uploadSourceKey || uploadMutation.isPending || !canRunImports}>
              Upload to inbox
            </button>
            {uploadMutation.isError ? <p className="form-status danger-text">{formatApiError(uploadMutation.error, "Upload blocked")}</p> : null}
          </form>
        </div>
      </section>

      <section className="work-panel">
        <h3>Inbox files</h3>
        <DataTable
          data={inbox.flatMap((batch) => batch.source_files.map((file) => ({ ...file, batch })))}
          emptyLabel="No files tracked in inbox"
          columns={[
            { header: "File", accessorKey: "original_filename" },
            { header: "Batch", cell: ({ row }) => row.original.batch.id.slice(0, 8) },
            { header: "Source", cell: ({ row }) => row.original.batch.source_key ?? "unmatched" },
            { header: "Status", accessorKey: "validation_status" },
            { header: "Storage", cell: ({ row }) => formatStatus(row.original.storage_status ?? "present") },
            { header: "Rows", accessorKey: "row_count" },
          ]}
        />
      </section>

      <section className="work-panel">
        <h3>Quarantine</h3>
        {blockedBatches.length ? (
          <DataTable
            data={blockedBatches}
            emptyLabel="No quarantined files"
            columns={[
              { header: "Batch", accessorKey: "id" },
              { header: "Source", accessorKey: "source_key" },
              { header: "Status", accessorKey: "status" },
              { header: "Validation", accessorKey: "validation_status" },
            ]}
          />
        ) : (
          <p className="empty-state">No quarantined files</p>
        )}
      </section>

      {voidTarget ? (
        <div className="modal-backdrop">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="void-upload-title">
            <h3 id="void-upload-title">Void upload</h3>
            <p className="modal-copy">
              Batch {voidTarget.id.slice(0, 8)} will be removed from the active import workflow. Stored files are
              preserved unless destruction is explicitly selected.
            </p>
            <form className="modal-form" onSubmit={confirmVoidUpload}>
              <label>
                Reason
                <textarea value={voidReason} onChange={(event) => setVoidReason(event.target.value)} />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={destroyStoredFiles}
                  onChange={(event) => setDestroyStoredFiles(event.target.checked)}
                />
                <span>Destroy stored files</span>
              </label>
              <div className="button-row">
                <button type="button" onClick={closeVoidDialog} disabled={voidMutation.isPending}>
                  Cancel
                </button>
                <button type="submit" className="danger-button" disabled={!voidReason.trim() || voidMutation.isPending}>
                  Confirm void
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function ValidationScreen({
  findings,
  operatorActor,
  operatorActorContext,
  elevatedModeActive,
}: {
  findings: ValidationFinding[];
  operatorActor: string;
  operatorActorContext: ActorContext;
  elevatedModeActive: boolean;
}) {
  const queryClient = useQueryClient();
  const [showCleared, setShowCleared] = useState(false);
  const [clearTarget, setClearTarget] = useState<ValidationFinding | null>(null);
  const [clearNote, setClearNote] = useState("");
  const [clearStatus, setClearStatus] = useState<string | null>(null);
  const visibleFindings = useMemo(
    () => (showCleared ? findings : findings.filter((finding) => finding.status === "open")),
    [findings, showCleared],
  );
  const clearMutation = useMutation({
    mutationFn: resolveValidationFinding,
    onSuccess: (body) => {
      setClearStatus("Validation finding cleared");
      setClearTarget(null);
      setClearNote("");
      queryClient.setQueryData<{ findings: ValidationFinding[] }>(["validation-findings"], (current) => {
        if (!current) {
          return current;
        }
        return {
          findings: current.findings.map((finding) =>
            finding.id === body.finding.id ? body.finding : finding,
          ),
        };
      });
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["validation-findings"] });
    },
    onError: (error) => setClearStatus(formatApiError(error, "Validation finding clear blocked")),
  });

  function openClearDialog(finding: ValidationFinding) {
    setClearTarget(finding);
    setClearNote("");
    setClearStatus(null);
  }

  function closeClearDialog() {
    setClearTarget(null);
    setClearNote("");
  }

  function confirmClearFinding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!clearTarget || !clearNote.trim()) {
      return;
    }
    clearMutation.mutate({
      findingId: clearTarget.id,
      note: clearNote,
      actor: operatorActor,
      actorContext: operatorActorContext,
    });
  }

  const columns = useMemo<ColumnDef<ValidationFinding>[]>(
    () => [
      { header: "Severity", accessorKey: "severity" },
      { header: "Code", accessorKey: "code" },
      { header: "Target", cell: ({ row }) => `${row.original.target_type}:${row.original.target_id ?? "none"}` },
      { header: "Message", accessorKey: "message" },
      { header: "Status", accessorKey: "status" },
      { header: "Affected reports", cell: ({ row }) => affectedReports(row.original) },
      {
        header: "Action",
        cell: ({ row }) => {
          const finding = row.original;
          const targetLabel = `${finding.target_type}:${finding.target_id ?? "none"}`;
          if (finding.status !== "open") {
            return <span className="muted-text">Cleared</span>;
          }
          if (finding.severity === "blocking") {
            return (
              <span className="muted-text">
                Active blockers must be fixed or voided before they can be cleared.
              </span>
            );
          }
          return (
            <button
              type="button"
              className="link-button"
              aria-label={`Clear ${finding.code} ${targetLabel}`}
              onClick={() => openClearDialog(finding)}
              disabled={clearMutation.isPending || elevatedModeActive}
            >
              Clear {finding.code}
            </button>
          );
        },
      },
    ],
    [clearMutation.isPending, elevatedModeActive],
  );

  return (
    <section className="screen" aria-labelledby="validation-heading">
      <div className="screen-heading">
        <p className="product-label">Validation queue</p>
        <h2 id="validation-heading">Validation Issues</h2>
      </div>
      <div className="action-row">
        <label className="checkbox-row inline-checkbox">
          <input type="checkbox" checked={showCleared} onChange={(event) => setShowCleared(event.target.checked)} />
          <span>Show cleared</span>
        </label>
      </div>
      {elevatedModeActive ? (
        <p className="form-status warn-text">Validation clearing is disabled while elevated mode is active.</p>
      ) : null}
      {clearStatus ? <p className={clearStatus === "Validation finding cleared" ? "form-status ok-text" : "form-status danger-text"}>{clearStatus}</p> : null}
      <DataTable data={visibleFindings} columns={columns} emptyLabel="No open validation findings" />
      {clearTarget ? (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="clear-validation-title">
            <h3 id="clear-validation-title">Clear validation finding</h3>
            <p className="modal-copy">
              This records an acknowledgment event and removes the finding from the default open queue.
            </p>
            <form className="modal-form" onSubmit={confirmClearFinding}>
              <label>
                Clear note
                <textarea value={clearNote} onChange={(event) => setClearNote(event.target.value)} />
              </label>
              <div className="button-row">
                <button type="button" onClick={closeClearDialog} disabled={clearMutation.isPending}>
                  Cancel
                </button>
                <button type="submit" disabled={!clearNote.trim() || clearMutation.isPending}>
                  Confirm clear
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function ReviewScreen({
  transactions,
  selectedTransaction,
  selectedTransactionId,
  categories,
  operatorActor,
  operatorActorContext,
  canSaveReview,
  reviewSuggestionAllowed,
  elevatedModeActive,
  approvalModeEnabled,
  onSelectTransaction,
}: {
  transactions: Transaction[];
  selectedTransaction: TransactionDetail | Transaction | null;
  selectedTransactionId: string | null;
  categories: Category[];
  operatorActor: string;
  operatorActorContext: ActorContext;
  canSaveReview: boolean;
  reviewSuggestionAllowed: boolean;
  elevatedModeActive: boolean;
  approvalModeEnabled: boolean;
  onSelectTransaction: (id: string) => void;
}) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();
  const [statusFilter, setStatusFilter] = useState("all");
  const [validationFilter, setValidationFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [categorySelection, setCategorySelection] = useState("");
  const [otherCategory, setOtherCategory] = useState("");
  const [notes, setNotes] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [suggestionActionStatus, setSuggestionActionStatus] = useState<string | null>(null);
  const lastInitializedTransactionId = useRef<string | null>(null);
  const suggestionsQuery = useQuery({
    queryKey: ["suggestions", "active"],
    queryFn: () => fetchSuggestions({ status: "active" }),
  });
  const pendingSuggestions = suggestionsQuery.data?.suggestions ?? [];
  const categoryOptions = useMemo(() => categories.filter((category) => category.active), [categories]);
  const fallbackCategoryLabels = useMemo(
    () =>
      uniqueExistingListValues([
        ...transactions.flatMap((transaction) => [transaction.category_current, transaction.initial_category]),
        selectedTransaction?.category_current,
        selectedTransaction?.initial_category,
        ...(hasImportedFacts(selectedTransaction)
          ? selectedTransaction.imported_facts?.map((fact) => fact.initial_category) ?? []
          : []),
      ]),
    [selectedTransaction, transactions],
  );

  useLayoutEffect(() => {
    const currentCategory = selectedTransaction?.category_current?.trim() ?? "";
    const currentCategoryKey = selectedTransaction?.category_key_current?.trim() ?? "";
    if (!selectedTransaction) {
      lastInitializedTransactionId.current = null;
      setCategorySelection("");
      setOtherCategory("");
      setNotes("");
      setSaveStatus(null);
      return;
    }
    if (lastInitializedTransactionId.current === selectedTransaction.id) {
      return;
    }
    lastInitializedTransactionId.current = selectedTransaction.id;
    if (currentCategoryKey && categoryOptions.some((category) => category.category_key === currentCategoryKey)) {
      setCategorySelection(currentCategoryKey);
      setOtherCategory("");
    } else if (!categoryOptions.length && currentCategory && fallbackCategoryLabels.includes(currentCategory)) {
      setCategorySelection(currentCategory);
      setOtherCategory("");
    } else if (currentCategory) {
      setCategorySelection(OTHER_LIST_VALUE);
      setOtherCategory(currentCategory);
    } else {
      setCategorySelection(categoryOptions[0]?.category_key ?? fallbackCategoryLabels[0] ?? OTHER_LIST_VALUE);
      setOtherCategory("");
    }
    setNotes("");
    setSaveStatus(null);
  }, [categoryOptions, fallbackCategoryLabels, selectedTransaction]);

  const filteredTransactions = useMemo(
    () =>
      transactions.filter((transaction) => {
        const matchesReview = statusFilter === "all" || transaction.review_status === statusFilter;
        const matchesValidation = validationFilter === "all" || transaction.validation_status === validationFilter;
        const matchesSearch =
          !search.trim() ||
          `${transaction.raw_description ?? ""} ${transaction.category_current ?? ""}`
            .toLowerCase()
            .includes(search.trim().toLowerCase());
        return matchesReview && matchesValidation && matchesSearch;
      }),
    [search, statusFilter, transactions, validationFilter],
  );

  useEffect(() => {
    if (!filteredTransactions.length) {
      return;
    }
    const selectedIsVisible = filteredTransactions.some((transaction) => transaction.id === selectedTransactionId);
    if (!selectedIsVisible) {
      onSelectTransaction(filteredTransactions[0].id);
    }
  }, [filteredTransactions, onSelectTransaction, selectedTransactionId]);

  const otherCategorySelected = categorySelection === OTHER_LIST_VALUE;
  const approvedCategoryKey = otherCategorySelected ? "" : categorySelection.trim();
  const otherCategoryRequiresNote = otherCategorySelected;
  const currentCategory = selectedTransaction?.category_current?.trim() ?? "";
  const currentCategoryKey = selectedTransaction?.category_key_current?.trim() ?? currentCategory;
  const selectedTransactionBlocked = selectedTransaction?.validation_status === "blocked";
  const categoryChanged = Boolean(selectedTransaction) && (
    otherCategorySelected ? otherCategory.trim() !== currentCategory : approvedCategoryKey !== currentCategoryKey
  );
  const reviewAlreadyComplete = ["reviewed", "approved"].includes(selectedTransaction?.review_status ?? "");
  const reviewApprovalNeeded = Boolean(selectedTransaction) && !categoryChanged && !reviewAlreadyComplete;

  const decisionMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTransaction) {
        throw new Error("No selected transaction");
      }
      if (categoryChanged) {
        const categoryKey = otherCategorySelected
          ? (await createCategory({
              displayName: otherCategory,
              note: notes || t("review.customCategoryNote"),
              actor: operatorActor,
            })).category.category_key
          : approvedCategoryKey;
        return saveCategoryDecision({
          transactionId: selectedTransaction.id,
          approvedCategoryKey: categoryKey,
          actor: operatorActor,
          actorContext: operatorActorContext,
          notes: otherCategoryRequiresNote ? notes.trim() : notes,
        });
      }
      return saveReviewStatusDecision({
        transactionId: selectedTransaction.id,
        approvedStatus: "reviewed",
        actor: operatorActor,
        actorContext: operatorActorContext,
        notes,
      });
    },
    onSuccess: (body) => {
      setSaveStatus(t("review.decisionSaved"));
      const updatedCategory = body.current_state?.category_current ?? currentCategory;
      const updatedCategoryKey = body.current_state?.category_key_current ?? approvedCategoryKey;
      queryClient.setQueryData<{ transactions: Transaction[] }>(["transactions"], (current) => {
        if (!current) {
          return current;
        }
        return {
          transactions: current.transactions.map((transaction) =>
            transaction.id === selectedTransactionId
              ? {
                  ...transaction,
                  category_key_current: updatedCategoryKey,
                  category_current: updatedCategory,
                  review_status: body.current_state?.review_status ?? transaction.review_status,
                }
              : transaction,
          ),
        };
      });
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["transaction", selectedTransactionId] });
      void queryClient.invalidateQueries({ queryKey: ["categories"] });
    },
    onError: (error) => setSaveStatus(formatApiError(error, "Decision blocked")),
  });

  const suggestionMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTransaction) {
        throw new Error("No selected transaction");
      }
      const categoryKey = otherCategorySelected
        ? (await createCategory({
            displayName: otherCategory,
            note: notes || t("review.customCategoryNote"),
            actor: operatorActor,
          })).category.category_key
        : approvedCategoryKey;
      const decisionType = categoryChanged ? "category_change" : "review_status_change";
      const fieldName = categoryChanged ? "category" : "review_status";
      const proposedValue = categoryChanged ? categoryKey : "reviewed";
      return createSuggestion({
        targetType: "canonical_transaction",
        targetId: selectedTransaction.id,
        actionKey: "review.decide",
        decisionType,
        fieldName,
        proposedValue,
        actor: operatorActor,
        actorContext: operatorActorContext,
        notes,
      });
    },
    onSuccess: () => {
      setSaveStatus("Suggestion submitted");
      void queryClient.invalidateQueries({ queryKey: ["suggestions"] });
    },
    onError: (error) => setSaveStatus(formatApiError(error, "Suggestion blocked")),
  });

  const acceptSuggestionMutation = useMutation({
    mutationFn: acceptSuggestion,
    onSuccess: () => {
      setSuggestionActionStatus("Suggestion accepted");
      void queryClient.invalidateQueries({ queryKey: ["suggestions"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
    },
    onError: (error) => setSuggestionActionStatus(formatApiError(error, "Suggestion accept blocked")),
  });

  const dismissSuggestionMutation = useMutation({
    mutationFn: dismissSuggestion,
    onSuccess: () => {
      setSuggestionActionStatus("Suggestion dismissed");
      void queryClient.invalidateQueries({ queryKey: ["suggestions"] });
    },
    onError: (error) => setSuggestionActionStatus(formatApiError(error, "Suggestion dismiss blocked")),
  });

  const convertSuggestionMutation = useMutation({
    mutationFn: convertSuggestionToApproval,
    onSuccess: () => {
      setSuggestionActionStatus("Suggestion converted to approval request");
      void queryClient.invalidateQueries({ queryKey: ["suggestions"] });
      void queryClient.invalidateQueries({ queryKey: ["approval-requests"] });
    },
    onError: (error) => setSuggestionActionStatus(formatApiError(error, "Suggestion conversion blocked")),
  });

  const saveDecisionDisabled =
    !selectedTransaction ||
    selectedTransactionBlocked ||
    decisionMutation.isPending ||
    !canSaveReview ||
    (!otherCategorySelected && !approvedCategoryKey) ||
    (otherCategorySelected && !otherCategory.trim()) ||
    (otherCategoryRequiresNote && !notes.trim()) ||
    (!categoryChanged && !reviewApprovalNeeded);

  const submitSuggestionDisabled =
    !selectedTransaction ||
    selectedTransactionBlocked ||
    suggestionMutation.isPending ||
    !reviewSuggestionAllowed ||
    canSaveReview ||
    elevatedModeActive ||
    (!otherCategorySelected && !approvedCategoryKey) ||
    (otherCategorySelected && !otherCategory.trim()) ||
    (otherCategoryRequiresNote && !notes.trim()) ||
    (!categoryChanged && !reviewApprovalNeeded);

  const suggestionActionPending =
    acceptSuggestionMutation.isPending ||
    dismissSuggestionMutation.isPending ||
    convertSuggestionMutation.isPending;

  const columns = useMemo<ColumnDef<Transaction>[]>(
    () => [
      { header: "Date", accessorKey: "posted_date" },
      { header: "Description", accessorKey: "raw_description" },
      { header: "Amount", accessorKey: "amount" },
      { header: "Category", accessorKey: "category_current" },
      { header: "Review", accessorKey: "review_status" },
      { header: "Validation", accessorKey: "validation_status" },
      {
        header: "Action",
        cell: ({ row }) => (
          <button type="button" className="link-button" onClick={() => onSelectTransaction(row.original.id)}>
            Select
          </button>
        ),
      },
    ],
    [onSelectTransaction],
  );

  function saveDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      !selectedTransaction ||
      (!otherCategorySelected && !approvedCategoryKey) ||
      (otherCategorySelected && !otherCategory.trim()) ||
      (otherCategoryRequiresNote && !notes.trim()) ||
      (!categoryChanged && !reviewApprovalNeeded)
    ) {
      return;
    }
    decisionMutation.mutate();
  }

  return (
    <section className="screen" aria-labelledby="review-heading">
      <div className="screen-heading">
        <p className="product-label">Controlled decision queue</p>
        <h2 id="review-heading">Ledger Review</h2>
      </div>

      <div className="filters" aria-label="Review filters">
        <label>
          Search
          <input value={search} onChange={(event) => setSearch(event.target.value)} />
        </label>
        <label>
          Review status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="unreviewed">Unreviewed</option>
            <option value="reviewed">Reviewed</option>
          </select>
        </label>
        <label>
          Validation status
          <select value={validationFilter} onChange={(event) => setValidationFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="ready_for_review">Ready</option>
            <option value="blocked">Blocked</option>
          </select>
        </label>
      </div>

      <SuggestionsQueuePanel
        suggestions={pendingSuggestions}
        transactions={transactions}
        operatorActor={operatorActor}
        operatorActorContext={operatorActorContext}
        canManageSuggestions={canSaveReview}
        approvalModeEnabled={approvalModeEnabled}
        actionStatus={suggestionActionStatus}
        actionPending={suggestionActionPending}
        onAccept={(suggestionId) =>
          acceptSuggestionMutation.mutate({
            suggestionId,
            actor: operatorActor,
            actorContext: operatorActorContext,
          })
        }
        onDismiss={(suggestionId) =>
          dismissSuggestionMutation.mutate({
            suggestionId,
            actor: operatorActor,
            actorContext: operatorActorContext,
          })
        }
        onConvert={(suggestionId) =>
          convertSuggestionMutation.mutate({
            suggestionId,
            actor: operatorActor,
            actorContext: operatorActorContext,
          })
        }
      />

      <div className="review-layout">
        <section className="work-panel" aria-label="Review queue">
          <DataTable data={filteredTransactions} columns={columns} emptyLabel="No transactions ready for review" />
        </section>

        <form className="decision-editor" onSubmit={saveDecision}>
          <div className="decision-header">
            <div>
              <p className="product-label">Selected transaction</p>
              <h3>{selectedTransaction ? "Decision proposal" : "No transaction selected"}</h3>
            </div>
            <StatusBadge status={selectedTransaction?.validation_status ?? "not_loaded"} />
          </div>

          <dl className="detail-list">
            <div>
              <dt>Amount</dt>
              <dd>{selectedTransaction?.amount ?? "-"}</dd>
            </div>
            <div>
              <dt>Merchant</dt>
              <dd>{selectedTransaction?.normalized_merchant ?? "unconfirmed"}</dd>
            </div>
            <div>
              <dt>Imported facts</dt>
              <dd>{selectedTransaction?.imported_fact_count ?? 0}</dd>
            </div>
          </dl>

          <label>
            {t("review.currentCategory")}
            <input type="text" value={selectedTransaction?.category_current ?? ""} readOnly />
          </label>

          <label>
            {t("review.approvedCategory")}
            <select
              value={categorySelection}
              onChange={(event) => {
                setCategorySelection(event.target.value);
                if (event.target.value !== OTHER_LIST_VALUE) {
                  setOtherCategory("");
                }
              }}
            >
              {categoryOptions.map((category) => (
                <option key={category.category_key} value={category.category_key}>
                  {category.display_name}
                </option>
              ))}
              {!categoryOptions.length
                ? fallbackCategoryLabels.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))
                : null}
              <option value={OTHER_LIST_VALUE}>{t("review.other")}</option>
            </select>
          </label>

          {otherCategorySelected ? (
            <label>
              {t("review.otherCategory")}
              <input type="text" value={otherCategory} onChange={(event) => setOtherCategory(event.target.value)} />
            </label>
          ) : null}

          <label>
            {t("review.notes")}
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} required={otherCategoryRequiresNote} />
          </label>

          <div className="audit-preview" aria-label="Audit preview">
            <span>Target: canonical transaction</span>
            <span>Actor: {operatorActorContext.display_name}</span>
            <span>Persona: {operatorActorContext.persona_label ?? operatorActorContext.persona_key}</span>
            <span>Source: owner</span>
          </div>

          {selectedTransactionBlocked ? (
            <p className="form-status danger-text">
              Blocked transactions must be resolved in Validation Issues before review decisions can be saved.
            </p>
          ) : null}

          {reviewSuggestionAllowed && !canSaveReview ? (
            <p className="form-status warn-text">
              Contributor persona can suggest review changes, but direct save is disabled for this persona.
            </p>
          ) : null}

          {elevatedModeActive ? (
            <p className="form-status warn-text">Review decisions are disabled while elevated mode is active.</p>
          ) : null}

          <button type="submit" disabled={saveDecisionDisabled}>
            {selectedTransactionBlocked ? t("review.resolveValidationFirst") : t("review.saveDecision")}
          </button>
          {reviewSuggestionAllowed && !canSaveReview ? (
            <button type="button" disabled={submitSuggestionDisabled} onClick={() => suggestionMutation.mutate()}>
              Submit suggestion
            </button>
          ) : null}
          {saveStatus ? <p className={saveStatus === t("review.decisionSaved") ? "form-status ok-text" : "form-status danger-text"}>{saveStatus}</p> : null}
        </form>
      </div>
    </section>
  );
}

function TransactionsScreen({
  transactions,
  selectedTransaction,
  selectedTransactionId,
  onSelectTransaction,
}: {
  transactions: Transaction[];
  selectedTransaction: TransactionDetail | Transaction | null;
  selectedTransactionId: string | null;
  onSelectTransaction: (id: string) => void;
}) {
  const columns = useMemo<ColumnDef<Transaction>[]>(
    () => [
      { header: "Date", accessorKey: "posted_date" },
      { header: "Description", accessorKey: "raw_description" },
      { header: "Amount", accessorKey: "amount" },
      { header: "Current category", accessorKey: "category_current" },
      { header: "Review", accessorKey: "review_status" },
      { header: "Validation", accessorKey: "validation_status" },
      {
        header: "Action",
        cell: ({ row }) => (
          <button type="button" className="link-button" onClick={() => onSelectTransaction(row.original.id)}>
            Audit
          </button>
        ),
      },
    ],
    [onSelectTransaction],
  );
  const history = hasDecisionHistory(selectedTransaction) ? selectedTransaction.decision_history ?? [] : [];

  return (
    <section className="screen" aria-labelledby="transactions-heading">
      <div className="screen-heading split-heading">
        <div>
          <p className="product-label">Reviewed/current ledger view</p>
          <h2 id="transactions-heading">Transactions</h2>
        </div>
        <StatusBadge status={selectedTransactionId ? "selected" : "not_selected"} />
      </div>

      <div className="two-column wide-left">
        <section className="work-panel">
          <DataTable data={transactions} columns={columns} emptyLabel="No canonical transactions" />
        </section>

        <aside className="work-panel">
          <h3>Audit timeline</h3>
          {history.length ? (
            <ol className="timeline">
              {history.map((event) => (
                <li key={event.id}>
                  <span>{event.created_at}</span>
                  <strong>{formatStatus(event.field_name)}</strong>
                  <span>{event.actor_context?.display_name ?? event.actor ?? "Unknown actor"}</span>
                  <span>{event.approved_value ?? "cleared"}</span>
                  {event.notes ? <span>{event.notes}</span> : null}
                </li>
              ))}
            </ol>
          ) : (
            <p className="empty-state">No decision events recorded for the selected transaction</p>
          )}
        </aside>
      </div>
    </section>
  );
}

function ReportsScreen({
  summary,
  artifacts,
  operatorActor,
  operatorActorContext,
  canRunReports,
  canRunMonthlyClose,
  canCreateExports,
  elevatedModeActive,
}: {
  summary: OperatorSummary;
  artifacts: Artifact[];
  operatorActor: string;
  operatorActorContext: ActorContext;
  canRunReports: boolean;
  canRunMonthlyClose: boolean;
  canCreateExports: boolean;
  elevatedModeActive: boolean;
}) {
  const queryClient = useQueryClient();
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  const refreshReportState = () => {
    void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
    void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
  };
  const runReportsMutation = useMutation({
    mutationFn: runReports,
    onSuccess: () => {
      setActionStatus("Reports completed");
      refreshReportState();
    },
    onError: (error) => setActionStatus(formatApiError(error, "Reports blocked")),
  });
  const draftCloseMutation = useMutation({
    mutationFn: draftMonthlyClose,
    onSuccess: () => {
      setActionStatus("Draft close created");
      refreshReportState();
    },
    onError: (error) => setActionStatus(formatApiError(error, "Draft close blocked")),
  });
  const finalCloseMutation = useMutation({
    mutationFn: finalizeMonthlyClose,
    onSuccess: () => {
      setActionStatus("Final close finalized");
      refreshReportState();
    },
    onError: (error) => setActionStatus(formatApiError(error, "Final close blocked")),
  });
  const advisorExportMutation = useMutation({
    mutationFn: createAdvisorExport,
    onSuccess: () => {
      setActionStatus("Advisor export created");
      refreshReportState();
    },
    onError: (error) => setActionStatus(formatApiError(error, "Advisor export blocked")),
  });
  const actionPending =
    runReportsMutation.isPending ||
    draftCloseMutation.isPending ||
    finalCloseMutation.isPending ||
    advisorExportMutation.isPending;
  const artifactColumns = useMemo<ColumnDef<Artifact>[]>(
    () => [
      { header: "Title", cell: ({ row }) => row.original.title ?? formatStatus(row.original.artifact_type) },
      { header: "Type", cell: ({ row }) => formatStatus(row.original.artifact_type) },
      { header: "Sensitivity", cell: ({ row }) => formatStatus(row.original.sensitivity ?? "financial_sensitive") },
      { header: "Path", accessorKey: "path" },
      {
        header: "Action",
        cell: ({ row }) => (
          <a className="link-button" href={row.original.download_url}>
            Download
          </a>
        ),
      },
    ],
    [],
  );

  return (
    <section className="screen" aria-labelledby="reports-heading">
      <div className="screen-heading split-heading">
        <div>
          <p className="product-label">Reports and close readiness</p>
          <h2 id="reports-heading">Reports & Monthly Close</h2>
        </div>
        <StatusBadge status={summary.monthly_close.ready_for_final ? "ready" : "not_ready"} />
      </div>

      <div className="metric-grid compact">
        <Metric label="Draft close" value={summary.monthly_close.ready_for_draft ? "Allowed" : "Blocked"} detail={summary.monthly_close.status} />
        <Metric label="Final close" value={summary.monthly_close.ready_for_final ? "Allowed" : "Blocked"} detail={`${summary.monthly_close.blockers.length} blocker(s)`} />
        <Metric label="Artifacts" value={artifacts.length || summary.artifacts?.generated_count || 0} detail="Generated files" />
      </div>

      <section className="work-panel">
        <h3>Report actions</h3>
        {elevatedModeActive ? (
          <p className="form-status warn-text">Report and close actions are disabled while elevated mode is active.</p>
        ) : null}
        <div className="action-row">
          <button
            type="button"
            onClick={() => runReportsMutation.mutate({ actor: operatorActor, actorContext: operatorActorContext })}
            disabled={actionPending || !canRunReports}
          >
            Run reports
          </button>
          <button
            type="button"
            onClick={() => draftCloseMutation.mutate({ actor: operatorActor, actorContext: operatorActorContext })}
            disabled={actionPending || !canRunMonthlyClose}
          >
            Draft close
          </button>
          <button
            type="button"
            onClick={() => finalCloseMutation.mutate({ actor: operatorActor, actorContext: operatorActorContext })}
            disabled={actionPending || !canRunMonthlyClose}
          >
            Final close
          </button>
          <button
            type="button"
            onClick={() => advisorExportMutation.mutate({ actor: operatorActor, actorContext: operatorActorContext })}
            disabled={actionPending || !canCreateExports}
          >
            Advisor export
          </button>
        </div>
        {actionStatus ? <p className="save-status">{actionStatus}</p> : null}
      </section>

      <section className="work-panel">
        <h3>Artifact registry</h3>
        <DataTable data={artifacts} columns={artifactColumns} emptyLabel="No generated artifacts" />
      </section>

      <section className="work-panel">
        <h3>Readiness blockers</h3>
        {summary.monthly_close.blockers.length ? (
          <ul className="plain-list">
            {summary.monthly_close.blockers.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        ) : (
          <p className="empty-state">No close blockers reported by current state</p>
        )}
      </section>
    </section>
  );
}

function SettingsScreen({
  settings,
  runtime,
  profiles,
  operatorActor,
  operatorActorContext,
  canSaveSettings,
  approvalModeEnabled,
  canManageApprovals,
  qaControlsEnabled,
  actors,
}: {
  settings?: SettingsPayload;
  runtime: RuntimeStatus;
  profiles: SourceProfile[];
  operatorActor: string;
  operatorActorContext: ActorContext;
  canSaveSettings: boolean;
  approvalModeEnabled: boolean;
  canManageApprovals: boolean;
  qaControlsEnabled?: boolean;
  actors?: ActorsPayload;
}) {
  const queryClient = useQueryClient();
  const activeProfiles = settings?.source_profiles ?? profiles;
  const editableSettings = useMemo(
    () => (settings?.settings ?? []).filter((setting) => setting.editable),
    [settings?.settings],
  );
  const [showReadOnlySettings, setShowReadOnlySettings] = useState(false);
  const [settingColumnVisibility, setSettingColumnVisibility] = useState({
    changed: false,
    domain: false,
    settingKey: false,
    editable: false,
  });
  const visibleSettings = useMemo(
    () => (showReadOnlySettings ? settings?.settings ?? [] : editableSettings),
    [editableSettings, settings?.settings, showReadOnlySettings],
  );
  const pendingProfiles = activeProfiles.filter((profile) => profile.confirmation_status === "pending_owner_sample");
  const [selectedSettingKey, setSelectedSettingKey] = useState(editableSettings[0]?.setting_key ?? "");
  const selectedSetting = editableSettings.find((setting) => setting.setting_key === selectedSettingKey);
  const [settingDraftValue, setSettingDraftValue] = useState("");
  const [settingNote, setSettingNote] = useState("");
  const [settingStatus, setSettingStatus] = useState<string | null>(null);
  const [selectedSourceKey, setSelectedSourceKey] = useState(pendingProfiles[0]?.source_key ?? "");
  const [confirmationNote, setConfirmationNote] = useState("");
  const [confirmationStatus, setConfirmationStatus] = useState<string | null>(null);
  const settingsColumns = useMemo<ColumnDef<SettingRow>[]>(() => {
    const columns: ColumnDef<SettingRow>[] = [
      { header: "Friendly name", cell: ({ row }) => settingLabel(row.original) },
      { header: "Value", cell: ({ row }) => formatSettingValue(row.original.value) },
      { header: "Default Value", cell: ({ row }) => formatSettingValue(row.original.default_value) },
    ];
    if (settingColumnVisibility.changed) {
      columns.push({ header: "Changed", cell: ({ row }) => (row.original.changed_from_default ? "Yes" : "No") });
    }
    if (settingColumnVisibility.domain) {
      columns.push({ header: "Domain", accessorKey: "domain" });
    }
    if (settingColumnVisibility.settingKey) {
      columns.push({ header: "Setting key", accessorKey: "setting_key" });
    }
    if (settingColumnVisibility.editable) {
      columns.push({ header: "Editable", cell: ({ row }) => (row.original.editable ? "Yes" : "No") });
    }
    return columns;
  }, [settingColumnVisibility]);

  useEffect(() => {
    if (!selectedSettingKey && editableSettings.length > 0) {
      setSelectedSettingKey(editableSettings[0].setting_key);
    }
    if (selectedSettingKey && !editableSettings.some((setting) => setting.setting_key === selectedSettingKey)) {
      setSelectedSettingKey(editableSettings[0]?.setting_key ?? "");
    }
  }, [editableSettings, selectedSettingKey]);

  useEffect(() => {
    if (selectedSetting) {
      setSettingDraftValue(settingValueToInput(selectedSetting.value));
    }
  }, [selectedSetting]);

  useEffect(() => {
    if (!selectedSourceKey && pendingProfiles.length > 0) {
      setSelectedSourceKey(pendingProfiles[0].source_key);
    }
    if (selectedSourceKey && !pendingProfiles.some((profile) => profile.source_key === selectedSourceKey)) {
      setSelectedSourceKey(pendingProfiles[0]?.source_key ?? "");
    }
  }, [pendingProfiles, selectedSourceKey]);

  const confirmationMutation = useMutation({
    mutationFn: confirmSourceProfileSample,
    onSuccess: (body) => {
      setConfirmationStatus("Source confirmation saved");
      setConfirmationNote("");
      queryClient.setQueryData(["settings"], body);
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
    },
    onError: (error) => setConfirmationStatus(formatApiError(error, "Source confirmation blocked")),
  });

  const settingMutation = useMutation({
    mutationFn: saveSettingChange,
    onSuccess: (body) => {
      setSettingStatus("Setting saved");
      setSettingNote("");
      queryClient.setQueryData(["settings"], body);
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
    },
    onError: (error) => setSettingStatus(formatApiError(error, "Setting save blocked")),
  });

  function saveEditableSetting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSetting) {
      return;
    }
    if (selectedSetting.note_required && !settingNote.trim()) {
      return;
    }
    settingMutation.mutate({
      domain: selectedSetting.domain,
      settingKey: selectedSetting.setting_key,
      value: inputToSettingValue(settingDraftValue, selectedSetting.value),
      actor: operatorActor,
      actorContext: operatorActorContext,
      note: settingNote,
    });
  }

  function saveSourceConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSourceKey || !confirmationNote.trim()) {
      return;
    }
    confirmationMutation.mutate({
      sourceKey: selectedSourceKey,
      actor: operatorActor,
      actorContext: operatorActorContext,
      note: confirmationNote,
    });
  }

  return (
    <section className="screen" aria-labelledby="settings-heading">
      <div className="screen-heading">
        <p className="product-label">Database-backed configuration</p>
        <h2 id="settings-heading">Settings</h2>
      </div>

      <div className="tabs" role="tablist" aria-label="Settings sections">
        {(settings?.tabs ?? []).map((tab, index) => (
          <button key={tab} type="button" role="tab" aria-selected={index === 0} className={index === 0 ? "active" : undefined}>
            {tab}
          </button>
        ))}
      </div>

      <section className="work-panel environment-panel" aria-label="Runtime environment">
        <h3>Environment</h3>
        <dl>
          <div>
            <dt>Environment</dt>
            <dd>{runtime.app_env_label}</dd>
          </div>
          <div>
            <dt>Dataset</dt>
            <dd>{runtime.dataset_kind}</dd>
          </div>
          <div>
            <dt>Data root</dt>
            <dd>{runtime.data_root.path}</dd>
          </div>
          <div>
            <dt>Database</dt>
            <dd>{runtime.database?.status ?? "unknown"}</dd>
          </div>
          <div>
            <dt>Local only</dt>
            <dd>{runtime.local_only ? "Yes" : "No"}</dd>
          </div>
          <div>
            <dt>Dev mode</dt>
            <dd>{runtime.dev_mode ? "On" : "Off"}</dd>
          </div>
        </dl>
      </section>

      {qaControlsEnabled ? <PermissionPreviewPanel actors={actors} /> : null}

      <div className="two-column">
        <section className="work-panel">
          <h3>Active settings</h3>
          {editableSettings.length ? (
            <form className="settings-form" onSubmit={saveEditableSetting}>
              <label>
                Editable setting
                <select value={selectedSettingKey} onChange={(event) => setSelectedSettingKey(event.target.value)}>
                  {editableSettings.map((setting) => (
                    <option key={setting.id} value={setting.setting_key}>
                      {settingLabel(setting)}
                    </option>
                  ))}
                </select>
              </label>
              {selectedSetting ? (
                <label>
                  Setting value
                  {typeof selectedSetting.value === "boolean" ? (
                    <select value={settingDraftValue} onChange={(event) => setSettingDraftValue(event.target.value)}>
                      <option value="true">True</option>
                      <option value="false">False</option>
                    </select>
                  ) : (
                    <input
                      type={typeof selectedSetting.value === "number" ? "number" : "text"}
                      value={settingDraftValue}
                      onChange={(event) => setSettingDraftValue(event.target.value)}
                    />
                  )}
                </label>
              ) : null}
              <label>
                Change note
                <textarea
                  value={settingNote}
                  onChange={(event) => setSettingNote(event.target.value)}
                  rows={3}
                />
              </label>
              <button
                type="submit"
                disabled={
                  !selectedSetting ||
                  (selectedSetting.note_required && !settingNote.trim()) ||
                  settingMutation.isPending ||
                  !canSaveSettings
                }
              >
                Save setting
              </button>
              {settingStatus ? <p className="form-status">{settingStatus}</p> : null}
            </form>
          ) : (
            <p className="empty-state">No editable settings loaded</p>
          )}
          <DataTable data={visibleSettings} emptyLabel="No settings loaded" columns={settingsColumns} />
          <div className="settings-view-controls" aria-label="Settings table view controls">
            <label>
              <input
                type="checkbox"
                checked={showReadOnlySettings}
                onChange={(event) => setShowReadOnlySettings(event.target.checked)}
              />
              Show read-only settings
            </label>
            <label>
              <input
                type="checkbox"
                checked={settingColumnVisibility.changed}
                onChange={(event) =>
                  setSettingColumnVisibility((current) => ({ ...current, changed: event.target.checked }))
                }
              />
              Show changed column
            </label>
            <label>
              <input
                type="checkbox"
                checked={settingColumnVisibility.domain}
                onChange={(event) =>
                  setSettingColumnVisibility((current) => ({ ...current, domain: event.target.checked }))
                }
              />
              Show domain column
            </label>
            <label>
              <input
                type="checkbox"
                checked={settingColumnVisibility.settingKey}
                onChange={(event) =>
                  setSettingColumnVisibility((current) => ({ ...current, settingKey: event.target.checked }))
                }
              />
              Show setting key column
            </label>
            <label>
              <input
                type="checkbox"
                checked={settingColumnVisibility.editable}
                onChange={(event) =>
                  setSettingColumnVisibility((current) => ({ ...current, editable: event.target.checked }))
                }
              />
              Show editable column
            </label>
          </div>
        </section>

        <section className="work-panel">
          <h3>Source profiles</h3>
          {pendingProfiles.length ? (
            <form className="settings-form" onSubmit={saveSourceConfirmation}>
              <div className="form-banner warn-text">Parser sample confirmation needed</div>
              <label>
                Source profile
                <select value={selectedSourceKey} onChange={(event) => setSelectedSourceKey(event.target.value)}>
                  {pendingProfiles.map((profile) => (
                    <option key={profile.source_key} value={profile.source_key}>
                      {profile.display_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Owner confirmation note
                <textarea
                  value={confirmationNote}
                  onChange={(event) => setConfirmationNote(event.target.value)}
                  rows={3}
                />
              </label>
              <button
                type="submit"
                disabled={!selectedSourceKey || !confirmationNote.trim() || confirmationMutation.isPending || !canSaveSettings}
              >
                Confirm source sample
              </button>
              {confirmationStatus ? <p className="form-status">{confirmationStatus}</p> : null}
            </form>
          ) : (
            <p className="empty-state">No source profile samples pending confirmation</p>
          )}
          <DataTable
            data={activeProfiles}
            emptyLabel="No source profiles loaded"
            columns={[
              { header: "Source", accessorKey: "display_name" },
              { header: "Type", accessorKey: "account_type" },
              { header: "Template", cell: ({ row }) => (row.original.is_template ? "Yes" : "No") },
              { header: "Enabled", cell: ({ row }) => (row.original.enabled ? "Yes" : "No") },
              { header: "Required", cell: ({ row }) => (row.original.required ? "Yes" : "No") },
              { header: "Confirmation", accessorKey: "confirmation_status" },
            ]}
          />
        </section>
      </div>

      <section className="work-panel">
        <h3>Settings audit history</h3>
        <DataTable
          data={settings?.settings_events ?? []}
          emptyLabel="No settings events recorded"
          columns={[
            { header: "When", accessorKey: "created_at" },
            { header: "Domain", accessorKey: "domain" },
            { header: "Setting", cell: ({ row }) => row.original.friendly_name || row.original.setting_key },
            { header: "Actor", accessorKey: "actor" },
            { header: "Notes", cell: ({ row }) => row.original.notes || "" },
          ]}
        />
      </section>

      {approvalModeEnabled ? (
        <ApprovalsQueuePanel
          operatorActor={operatorActor}
          operatorActorContext={operatorActorContext}
          canManageApprovals={canManageApprovals}
        />
      ) : null}
    </section>
  );
}

function SuggestionsQueuePanel({
  suggestions,
  transactions,
  operatorActor,
  operatorActorContext,
  canManageSuggestions,
  approvalModeEnabled,
  actionStatus,
  actionPending,
  onAccept,
  onDismiss,
  onConvert,
}: {
  suggestions: Suggestion[];
  transactions: Transaction[];
  operatorActor: string;
  operatorActorContext: ActorContext;
  canManageSuggestions: boolean;
  approvalModeEnabled: boolean;
  actionStatus: string | null;
  actionPending: boolean;
  onAccept: (suggestionId: string) => void;
  onDismiss: (suggestionId: string) => void;
  onConvert: (suggestionId: string) => void;
}) {
  const transactionById = useMemo(
    () => Object.fromEntries(transactions.map((transaction) => [transaction.id, transaction])),
    [transactions],
  );

  return (
    <section className="work-panel" aria-label="Pending suggestions">
      <h3>Pending suggestions</h3>
      {actionStatus ? (
        <p
          className={
            actionStatus.includes("blocked") ? "form-status danger-text" : "form-status ok-text"
          }
        >
          {actionStatus}
        </p>
      ) : null}
      <DataTable
        data={suggestions}
        emptyLabel="No pending suggestions"
        columns={[
          {
            header: "Transaction",
            cell: ({ row }) =>
              transactionById[row.original.target_id]?.raw_description ?? row.original.target_id.slice(0, 8),
          },
          { header: "Field", accessorKey: "field_name" },
          { header: "Proposed", accessorKey: "proposed_value" },
          { header: "Proposer", accessorKey: "proposer_actor" },
          { header: "Status", accessorKey: "status" },
          {
            header: "Actions",
            cell: ({ row }) =>
              canManageSuggestions ? (
                <div className="table-actions">
                  <button
                    type="button"
                    className="link-button"
                    disabled={actionPending}
                    onClick={() => onAccept(row.original.id)}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    disabled={actionPending}
                    onClick={() => onDismiss(row.original.id)}
                  >
                    Dismiss
                  </button>
                  {approvalModeEnabled ? (
                    <button
                      type="button"
                      className="link-button"
                      disabled={actionPending}
                      onClick={() => onConvert(row.original.id)}
                    >
                      Convert to approval
                    </button>
                  ) : null}
                </div>
              ) : (
                <span className="muted-text">Awaiting review</span>
              ),
          },
        ]}
      />
    </section>
  );
}

function ApprovalsQueuePanel({
  operatorActor,
  operatorActorContext,
  canManageApprovals,
}: {
  operatorActor: string;
  operatorActorContext: ActorContext;
  canManageApprovals: boolean;
}) {
  const queryClient = useQueryClient();
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const approvalsQuery = useQuery({
    queryKey: ["approval-requests", "pending"],
    queryFn: () => fetchApprovalRequests({ status: "pending" }),
    enabled: canManageApprovals,
  });
  const pendingApprovals = approvalsQuery.data?.approval_requests ?? [];

  const approveMutation = useMutation({
    mutationFn: approveApprovalRequest,
    onSuccess: () => {
      setActionStatus("Approval request approved");
      void queryClient.invalidateQueries({ queryKey: ["approval-requests"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
    },
    onError: (error) => setActionStatus(formatApiError(error, "Approval blocked")),
  });

  const rejectMutation = useMutation({
    mutationFn: rejectApprovalRequest,
    onSuccess: () => {
      setActionStatus("Approval request rejected");
      void queryClient.invalidateQueries({ queryKey: ["approval-requests"] });
    },
    onError: (error) => setActionStatus(formatApiError(error, "Rejection blocked")),
  });

  const cancelMutation = useMutation({
    mutationFn: cancelApprovalRequest,
    onSuccess: () => {
      setActionStatus("Approval request cancelled");
      void queryClient.invalidateQueries({ queryKey: ["approval-requests"] });
    },
    onError: (error) => setActionStatus(formatApiError(error, "Cancellation blocked")),
  });

  const actionPending = approveMutation.isPending || rejectMutation.isPending || cancelMutation.isPending;

  return (
    <section className="work-panel" aria-label="Approvals queue">
      <h3>Approvals queue</h3>
      {!canManageApprovals ? (
        <p className="form-status warn-text">Current persona cannot manage approval requests.</p>
      ) : null}
      {actionStatus ? (
        <p className={actionStatus.includes("blocked") ? "form-status danger-text" : "form-status ok-text"}>
          {actionStatus}
        </p>
      ) : null}
      <DataTable
        data={pendingApprovals}
        emptyLabel="No pending approval requests"
        columns={[
          { header: "Target", cell: ({ row }) => `${row.original.target_type}:${row.original.target_id.slice(0, 8)}` },
          { header: "Field", accessorKey: "field_name" },
          { header: "Proposed", accessorKey: "proposed_value" },
          { header: "Trigger", accessorKey: "policy_trigger" },
          { header: "Proposer", accessorKey: "proposer_actor" },
          { header: "Expires", accessorKey: "expires_at" },
          {
            header: "Actions",
            cell: ({ row }) => (
              <div className="table-actions">
                <button
                  type="button"
                  className="link-button"
                  disabled={!canManageApprovals || actionPending || row.original.proposer_actor === operatorActor}
                  onClick={() =>
                    approveMutation.mutate({
                      approvalRequestId: row.original.id,
                      actor: operatorActor,
                      actorContext: operatorActorContext,
                    })
                  }
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="link-button"
                  disabled={!canManageApprovals || actionPending}
                  onClick={() =>
                    rejectMutation.mutate({
                      approvalRequestId: row.original.id,
                      actor: operatorActor,
                      actorContext: operatorActorContext,
                    })
                  }
                >
                  Reject
                </button>
                <button
                  type="button"
                  className="link-button"
                  disabled={!canManageApprovals || actionPending || row.original.proposer_actor !== operatorActor}
                  onClick={() =>
                    cancelMutation.mutate({
                      approvalRequestId: row.original.id,
                      actor: operatorActor,
                      actorContext: operatorActorContext,
                    })
                  }
                >
                  Cancel
                </button>
              </div>
            ),
          },
        ]}
      />
    </section>
  );
}

function DataTable<T>({ data, columns, emptyLabel }: { data: T[]; columns: ColumnDef<T>[]; emptyLabel: string }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (!data.length) {
    return <p className="empty-state">{emptyLabel}</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>{header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}</th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metric({ label, value, detail, tone }: { label: string; value: string | number; detail: string; tone?: "ok" | "warn" | "danger" }) {
  return (
    <article className={`metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone = status.includes("block") || status.includes("not") ? "danger" : status.includes("ready") || status.includes("accepted") ? "ok" : "warn";
  return <span className={`status-badge ${tone}`}>{formatStatus(status)}</span>;
}

function affectedReports(finding: ValidationFinding) {
  if (finding.severity === "blocking") {
    return "Import, review, monthly close";
  }
  return "Import and report readiness";
}

function hasDecisionHistory(transaction: TransactionDetail | Transaction | null): transaction is TransactionDetail {
  return Boolean(transaction && "decision_history" in transaction);
}

function hasImportedFacts(transaction: TransactionDetail | Transaction | null): transaction is TransactionDetail {
  return Boolean(transaction && "imported_facts" in transaction);
}

function formatStatus(status: string) {
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function settingValueToInput(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value ?? "");
}

function inputToSettingValue(input: string, currentValue: unknown) {
  if (typeof currentValue === "boolean") {
    return input === "true";
  }
  if (typeof currentValue === "number") {
    return Number(input);
  }
  if (typeof currentValue === "string") {
    return input;
  }
  try {
    return JSON.parse(input);
  } catch {
    return input;
  }
}

function settingLabel(setting: SettingsPayload["settings"][number]) {
  return setting.friendly_name || setting.setting_key;
}

function formatSettingValue(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
