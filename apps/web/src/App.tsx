import { FormEvent, useEffect, useMemo, useState } from "react";
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

import {
  acceptImportBatch,
  confirmSourceProfileSample,
  fetchOperatorSummary,
  createAdvisorExport,
  draftMonthlyClose,
  fetchArtifacts,
  fetchSettings,
  fetchTransactionDetail,
  fetchTransactions,
  fetchValidationFindings,
  finalizeMonthlyClose,
  runReports,
  saveCategoryDecision,
  scanInbox,
  uploadSourceFile,
  validateImportBatch,
} from "./api";
import type {
  Artifact,
  InboxScan,
  ImportBatch,
  OperatorSummary,
  SettingsPayload,
  SourceProfile,
  Transaction,
  TransactionDetail,
  ValidationFinding,
} from "./types";
import "./styles.css";

type ScreenKey = "home" | "sources" | "validation" | "review" | "transactions" | "reports" | "settings";

const screens: Array<{ key: ScreenKey; label: string }> = [
  { key: "home", label: "Home" },
  { key: "sources", label: "Sources" },
  { key: "validation", label: "Validation Issues" },
  { key: "review", label: "Review" },
  { key: "transactions", label: "Transactions" },
  { key: "reports", label: "Reports" },
  { key: "settings", label: "Settings" },
];

const emptySummary: OperatorSummary = {
  runtime: {
    app: "Dillon Finances",
    version: "0.1.0",
    local_only: true,
    bind_host: "127.0.0.1",
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

export function App() {
  const [queryClient] = useState(createQueryClient);

  return (
    <QueryClientProvider client={queryClient}>
      <OperatorApp />
    </QueryClientProvider>
  );
}

function OperatorApp() {
  const [activeScreen, setActiveScreen] = useState<ScreenKey>("home");
  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);

  const summaryQuery = useQuery({ queryKey: ["operator-summary"], queryFn: fetchOperatorSummary });
  const inboxQuery = useQuery({ queryKey: ["inbox-scan"], queryFn: scanInbox });
  const findingsQuery = useQuery({ queryKey: ["validation-findings"], queryFn: fetchValidationFindings });
  const transactionsQuery = useQuery({ queryKey: ["transactions"], queryFn: fetchTransactions });
  const settingsQuery = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const artifactsQuery = useQuery({ queryKey: ["artifacts"], queryFn: fetchArtifacts });

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
  const findings = findingsQuery.data?.findings ?? [];
  const inbox = inboxQuery.data?.import_batches ?? [];
  const settings = settingsQuery.data;
  const selectedTransaction =
    transactionDetailQuery.data?.transaction ??
    transactions.find((transaction) => transaction.id === selectedTransactionId) ??
    null;

  return (
    <div className="app-shell">
      <Header summary={summary} />

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
              {screen.label}
            </a>
          ))}
        </nav>

        <main className="content">
          {activeScreen === "home" ? <HomeScreen summary={summary} /> : null}
          {activeScreen === "sources" ? <SourcesScreen profiles={summary.sources.profiles} inbox={inbox} /> : null}
          {activeScreen === "validation" ? <ValidationScreen findings={findings} /> : null}
          {activeScreen === "review" ? (
            <ReviewScreen
              transactions={transactions}
              selectedTransaction={selectedTransaction}
              selectedTransactionId={selectedTransactionId}
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
            <ReportsScreen summary={summary} artifacts={artifactsQuery.data?.artifacts ?? []} />
          ) : null}
          {activeScreen === "settings" ? <SettingsScreen settings={settings} profiles={summary.sources.profiles} /> : null}
        </main>
      </div>
    </div>
  );
}

function Header({ summary }: { summary: OperatorSummary }) {
  return (
    <header className="topbar">
      <div>
        <p className="product-label">Family financial operating system</p>
        <h1>Dillon Finances</h1>
      </div>
      <div className="status-strip" aria-label="Runtime status">
        <span className={summary.runtime.local_only ? "ok" : "danger"}>Local browser mode</span>
        <span>{summary.runtime.bind_host}</span>
        <span>{summary.runtime.data_root.exists ? "DATA_ROOT mounted" : "DATA_ROOT unavailable"}</span>
        <span>Close: {formatStatus(summary.monthly_close.status)}</span>
      </div>
    </header>
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

function SourcesScreen({ profiles, inbox }: { profiles: SourceProfile[]; inbox: ImportBatch[] }) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [batchActionStatus, setBatchActionStatus] = useState<string | null>(null);

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
    onError: () => setBatchActionStatus("Batch validation blocked"),
  });
  const acceptMutation = useMutation({
    mutationFn: acceptImportBatch,
    onSuccess: (body) => {
      updateCachedBatch(body);
      setBatchActionStatus("Batch accepted");
      refreshAfterBatchAction();
    },
    onError: () => setBatchActionStatus("Batch acceptance blocked"),
  });

  const blockedBatches = inbox.filter((batch) => batch.status === "blocked" || batch.validation_status === "blocked");
  const batchActionPending = validateMutation.isPending || acceptMutation.isPending;

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
        <h3>Required sources</h3>
        <div className="source-grid">
          {profiles.map((profile) => (
            <article key={profile.source_key} className="source-card">
              <div>
                <h4>{profile.display_name}</h4>
                <span>{formatStatus(profile.account_type)}</span>
              </div>
              <dl>
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
                cell: ({ row }) => (
                  <div className="table-actions">
                    <button
                      type="button"
                      className="link-button"
                      disabled={batchActionPending}
                      onClick={() => validateMutation.mutate(row.original.id)}
                    >
                      Validate batch
                    </button>
                    <button
                      type="button"
                      className="link-button"
                      disabled={batchActionPending || row.original.validation_status === "pending"}
                      onClick={() => acceptMutation.mutate(row.original.id)}
                    >
                      Accept batch
                    </button>
                  </div>
                ),
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
              if (selectedFile) {
                uploadMutation.mutate(selectedFile);
              }
            }}
          >
            <label>
              Source file
              <input type="file" accept=".csv" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} />
            </label>
            <button type="submit" disabled={!selectedFile || uploadMutation.isPending}>
              Upload to inbox
            </button>
            {uploadMutation.isError ? <p className="form-status danger-text">Upload blocked</p> : null}
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
    </section>
  );
}

function ValidationScreen({ findings }: { findings: ValidationFinding[] }) {
  const columns = useMemo<ColumnDef<ValidationFinding>[]>(
    () => [
      { header: "Severity", accessorKey: "severity" },
      { header: "Code", accessorKey: "code" },
      { header: "Target", cell: ({ row }) => `${row.original.target_type}:${row.original.target_id ?? "none"}` },
      { header: "Message", accessorKey: "message" },
      { header: "Status", accessorKey: "status" },
      { header: "Affected reports", cell: ({ row }) => affectedReports(row.original) },
    ],
    [],
  );

  return (
    <section className="screen" aria-labelledby="validation-heading">
      <div className="screen-heading">
        <p className="product-label">Validation queue</p>
        <h2 id="validation-heading">Validation Issues</h2>
      </div>
      <DataTable data={findings} columns={columns} emptyLabel="No validation findings" />
    </section>
  );
}

function ReviewScreen({
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
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState("all");
  const [validationFilter, setValidationFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [approvedCategory, setApprovedCategory] = useState("");
  const [notes, setNotes] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  useEffect(() => {
    setApprovedCategory(selectedTransaction?.category_current ?? "");
    setNotes("");
    setSaveStatus(null);
  }, [selectedTransaction?.id, selectedTransaction?.category_current]);

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

  const decisionMutation = useMutation({
    mutationFn: saveCategoryDecision,
    onSuccess: (body) => {
      setSaveStatus("Decision saved");
      const updatedCategory = body.current_state?.category_current ?? approvedCategory.trim();
      queryClient.setQueryData<{ transactions: Transaction[] }>(["transactions"], (current) => {
        if (!current) {
          return current;
        }
        return {
          transactions: current.transactions.map((transaction) =>
            transaction.id === selectedTransactionId
              ? {
                  ...transaction,
                  category_current: updatedCategory,
                  review_status: body.current_state?.review_status ?? transaction.review_status,
                }
              : transaction,
          ),
        };
      });
      void queryClient.invalidateQueries({ queryKey: ["operator-summary"] });
      void queryClient.invalidateQueries({ queryKey: ["transaction", selectedTransactionId] });
    },
    onError: () => setSaveStatus("Decision blocked"),
  });

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
    if (!selectedTransaction || !approvedCategory.trim()) {
      return;
    }
    decisionMutation.mutate({
      transactionId: selectedTransaction.id,
      approvedCategory: approvedCategory.trim(),
      notes,
    });
  }

  const selectedIsBlocked = selectedTransaction?.validation_status === "blocked";

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
            Current category
            <input type="text" value={selectedTransaction?.category_current ?? ""} readOnly />
          </label>

          <label>
            Approved category
            <input type="text" value={approvedCategory} onChange={(event) => setApprovedCategory(event.target.value)} />
          </label>

          <label>
            Notes
            <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
          </label>

          <div className="audit-preview" aria-label="Audit preview">
            <span>Target: canonical transaction</span>
            <span>Actor: mason</span>
            <span>Source: owner</span>
          </div>

          <button type="submit" disabled={!selectedTransaction || selectedIsBlocked || decisionMutation.isPending}>
            Save decision
          </button>
          {saveStatus ? <p className={saveStatus === "Decision saved" ? "form-status ok-text" : "form-status danger-text"}>{saveStatus}</p> : null}
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
                  <span>{event.approved_value ?? "cleared"}</span>
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

function ReportsScreen({ summary, artifacts }: { summary: OperatorSummary; artifacts: Artifact[] }) {
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
    onError: () => setActionStatus("Reports blocked"),
  });
  const draftCloseMutation = useMutation({
    mutationFn: draftMonthlyClose,
    onSuccess: () => {
      setActionStatus("Draft close created");
      refreshReportState();
    },
    onError: () => setActionStatus("Draft close blocked"),
  });
  const finalCloseMutation = useMutation({
    mutationFn: finalizeMonthlyClose,
    onSuccess: () => {
      setActionStatus("Final close finalized");
      refreshReportState();
    },
    onError: () => setActionStatus("Final close blocked"),
  });
  const advisorExportMutation = useMutation({
    mutationFn: createAdvisorExport,
    onSuccess: () => {
      setActionStatus("Advisor export created");
      refreshReportState();
    },
    onError: () => setActionStatus("Advisor export blocked"),
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
        <div className="action-row">
          <button type="button" onClick={() => runReportsMutation.mutate()} disabled={actionPending}>
            Run reports
          </button>
          <button type="button" onClick={() => draftCloseMutation.mutate()} disabled={actionPending}>
            Draft close
          </button>
          <button type="button" onClick={() => finalCloseMutation.mutate()} disabled={actionPending}>
            Final close
          </button>
          <button type="button" onClick={() => advisorExportMutation.mutate()} disabled={actionPending}>
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

function SettingsScreen({ settings, profiles }: { settings?: SettingsPayload; profiles: SourceProfile[] }) {
  const queryClient = useQueryClient();
  const activeProfiles = settings?.source_profiles ?? profiles;
  const pendingProfiles = activeProfiles.filter((profile) => profile.confirmation_status === "pending_owner_sample");
  const [selectedSourceKey, setSelectedSourceKey] = useState(pendingProfiles[0]?.source_key ?? "");
  const [confirmationNote, setConfirmationNote] = useState("");
  const [confirmationStatus, setConfirmationStatus] = useState<string | null>(null);

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
    onError: () => setConfirmationStatus("Source confirmation blocked"),
  });

  function saveSourceConfirmation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSourceKey || !confirmationNote.trim()) {
      return;
    }
    confirmationMutation.mutate({
      sourceKey: selectedSourceKey,
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

      <div className="two-column">
        <section className="work-panel">
          <h3>Active settings</h3>
          <DataTable
            data={settings?.settings ?? []}
            emptyLabel="No settings loaded"
            columns={[
              { header: "Domain", accessorKey: "domain" },
              { header: "Setting", accessorKey: "setting_key" },
              { header: "Value", cell: ({ row }) => String(row.original.value) },
              { header: "Editable", cell: ({ row }) => (row.original.editable ? "Yes" : "No") },
            ]}
          />
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
                disabled={!selectedSourceKey || !confirmationNote.trim() || confirmationMutation.isPending}
              >
                Confirm source sample
              </button>
              {confirmationStatus ? <p className="form-status">{confirmationStatus}</p> : null}
            </form>
          ) : (
            <p className="empty-state">All required source samples are confirmed</p>
          )}
          <DataTable
            data={activeProfiles}
            emptyLabel="No source profiles loaded"
            columns={[
              { header: "Source", accessorKey: "display_name" },
              { header: "Type", accessorKey: "account_type" },
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
            { header: "Setting", accessorKey: "setting_key" },
            { header: "Actor", accessorKey: "actor" },
          ]}
        />
      </section>
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

function formatStatus(status: string) {
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
