import { FormEvent, useEffect, useMemo, useState } from "react";

import "./styles.css";

const navItems = ["Home", "Sources", "Review", "Transactions", "Reports", "Settings"];
const settingsTabs = ["Data root", "Sources", "Thresholds", "Reports", "Privacy", "Future integrations"];
const sourceProfiles = [
  { name: "Alliant Checking", type: "Checking", freshness: "14 days" },
  { name: "Alliant Savings", type: "Savings", freshness: "14 days" },
  { name: "Alliant Credit Card", type: "Credit card", freshness: "14 days" },
  { name: "Chase Prime Visa", type: "Credit card", freshness: "14 days" },
];

type Transaction = {
  id: string;
  raw_description: string | null;
  amount: string;
  category_current: string | null;
  review_status: string;
  validation_status: string;
};

export function App() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);
  const [approvedCategory, setApprovedCategory] = useState("");
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let isMounted = true;
    async function loadTransactions() {
      if (typeof fetch === "undefined") {
        return;
      }
      try {
        const response = await fetch("/api/transactions");
        if (!response.ok) {
          return;
        }
        const body = await response.json();
        if (!isMounted) {
          return;
        }
        const loadedTransactions = body.transactions ?? [];
        setTransactions(loadedTransactions);
        setSelectedTransactionId(loadedTransactions[0]?.id ?? null);
      } catch {
        if (isMounted) {
          setTransactions([]);
        }
      }
    }
    void loadTransactions();
    return () => {
      isMounted = false;
    };
  }, []);

  const selectedTransaction = useMemo(
    () => transactions.find((transaction) => transaction.id === selectedTransactionId) ?? null,
    [selectedTransactionId, transactions],
  );

  useEffect(() => {
    setApprovedCategory(selectedTransaction?.category_current ?? "");
    setSaveStatus(null);
  }, [selectedTransaction?.id]);

  async function saveDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedTransaction || !approvedCategory.trim()) {
      return;
    }
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const response = await fetch("/api/decision-events", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target_type: "canonical_transaction",
          target_id: selectedTransaction.id,
          decision_type: "category_change",
          field_name: "category",
          proposed_value: approvedCategory.trim(),
          approved_value: approvedCategory.trim(),
          actor: "mason",
          suggestion_source: "owner",
          explicit_user_action: true,
        }),
      });
      if (!response.ok) {
        setSaveStatus("Decision blocked");
        return;
      }
      const body = await response.json();
      const category = body.current_state?.category_current ?? approvedCategory.trim();
      setTransactions((currentTransactions) =>
        currentTransactions.map((transaction) =>
          transaction.id === selectedTransaction.id
            ? { ...transaction, category_current: category, review_status: body.current_state?.review_status ?? transaction.review_status }
            : transaction,
        ),
      );
      setSaveStatus("Decision saved");
    } catch {
      setSaveStatus("Decision blocked");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Family financial operating system</p>
          <h1>Dillon Finances</h1>
        </div>
        <div className="status-strip" aria-label="Runtime status">
          <span>Data: Local only</span>
          <span>DATA_ROOT: External mount required</span>
          <span>Last refresh: Not run</span>
          <span>Close: Not started</span>
        </div>
      </header>

      <div className="workspace">
        <nav className="sidebar" aria-label="Primary">
          {navItems.map((item) => (
            <a key={item} href={`#${item.toLowerCase().replaceAll(" ", "-")}`}>
              {item}
            </a>
          ))}
        </nav>

        <main className="content">
          <section className="status-panel" aria-labelledby="current-status">
            <div>
              <p className="eyebrow">Current status</p>
              <h2 id="current-status">Ready for scaffold verification</h2>
            </div>
            <p>
              App implementation has started with the local Docker shell only. Financial workflows remain
              gated behind later milestone PRs.
            </p>
          </section>

          <section className="grid" aria-label="Operator overview">
            <div>
              <h3>Data boundary</h3>
              <p>Runtime data must stay in DATA_ROOT outside git.</p>
            </div>
            <div>
              <h3>Validation</h3>
              <p>No imports have run. Synthetic tests drive the first milestone.</p>
            </div>
            <div>
              <h3>Next action</h3>
              <p>Complete scaffold, Docker, and repository safety checks.</p>
            </div>
          </section>

          <section className="review-panel" aria-labelledby="review-heading" id="review">
            <div className="section-heading">
              <p className="eyebrow">Controlled review</p>
              <h2 id="review-heading">Ledger Review</h2>
            </div>

            <div className="review-layout">
              <div className="review-list" aria-label="Review queue">
                {transactions.length === 0 ? (
                  <p className="empty-state">No transactions ready for review</p>
                ) : (
                  transactions.map((transaction) => (
                    <button
                      key={transaction.id}
                      type="button"
                      className={transaction.id === selectedTransactionId ? "selected" : undefined}
                      onClick={() => setSelectedTransactionId(transaction.id)}
                    >
                      <span>{transaction.raw_description ?? "Unlabeled transaction"}</span>
                      <span>{transaction.amount}</span>
                      <span>{transaction.category_current ?? "Uncategorized"}</span>
                    </button>
                  ))
                )}
              </div>

              <form className="decision-editor" onSubmit={saveDecision}>
                <div className="decision-header">
                  <div>
                    <p className="eyebrow">Selected transaction</p>
                    <h3>{selectedTransaction?.raw_description ?? "No transaction selected"}</h3>
                  </div>
                  <span>{selectedTransaction?.validation_status ?? "not_loaded"}</span>
                </div>

                <label>
                  Current category
                  <input
                    type="text"
                    value={selectedTransaction?.category_current ?? ""}
                    readOnly
                  />
                </label>

                <label>
                  Approved category
                  <input
                    type="text"
                    value={approvedCategory}
                    onChange={(event) => setApprovedCategory(event.target.value)}
                  />
                </label>

                <div className="audit-preview" aria-label="Audit preview">
                  <span>Target: canonical transaction</span>
                  <span>Actor: mason</span>
                  <span>Source: owner</span>
                </div>

                <button
                  type="submit"
                  disabled={!selectedTransaction || selectedTransaction.validation_status === "blocked" || isSaving}
                >
                  Save decision
                </button>
                {saveStatus ? <p className="save-status">{saveStatus}</p> : null}
              </form>
            </div>
          </section>

          <section className="settings-panel" aria-labelledby="settings-heading">
            <div className="section-heading">
              <p className="eyebrow">SQLite-backed configuration</p>
              <h2 id="settings-heading">Settings</h2>
            </div>
            <div className="tabs" role="tablist" aria-label="Settings sections">
              {settingsTabs.map((tab, index) => (
                <button
                  key={tab}
                  type="button"
                  role="tab"
                  aria-selected={index === 0}
                  className={index === 0 ? "active" : undefined}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="settings-grid" aria-label="Source profile defaults">
              {sourceProfiles.map((source) => (
                <article key={source.name}>
                  <h3>{source.name}</h3>
                  <dl>
                    <div>
                      <dt>Type</dt>
                      <dd>{source.type}</dd>
                    </div>
                    <div>
                      <dt>Required</dt>
                      <dd>Yes</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{source.freshness}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
