# v1.1 Interactive Mockups (visual-only)

Standalone, dependency-free HTML/CSS/JS mockups for the Family Finance OS v1.1 feature pass.
These are **planning artifacts**, not app code. There is no backend, no `fetch`, no build step, and
no npm dependencies. All dollar amounts are synthetic/redacted.

## What this is

A single page (`index.html`) that mirrors the real app frame (sidebar, status strip, design tokens
copied from `apps/web/src/styles.css`) and lets you click through the new v1.1 surfaces. Interactions
are **display-only** — toggles, tabs, wizard steps, and live math change what you see on screen but
do not read or write any data.

## How to open locally

Easiest — just open the file in a browser:

```bash
open planning/mockups/v1_1/index.html
```

Or serve the folder (handy if your browser blocks `file://` behavior):

```bash
cd planning/mockups/v1_1
python3 -m http.server 8000
# then visit http://127.0.0.1:8000/
```

## Screens and what to try

Use the left sidebar to switch screens. The order matches the approved v1.1 nav: Home, Funds,
Dashboard, Sources, Review, Transactions, Reports, Settings, plus an "Auth screens" preview.

- **Home (A)** — toggle **Include provisional exposure**; the headline number, label, and breakdown
  recompute live ($3,412.58 ↔ $1,570.58).
- **Funds (B)** — click **Demo overcommit warning** to flip the commitment-health card and reveal the
  overcommit warning band; click again to reset.
- **Dashboard (C)** — CSS/SVG-free bar charts (no Recharts); toggle **Include estimates** on the net
  worth tile to reveal the estimates warning band.
- **Split editor (D)** — reach it from Transactions/Review (contextual). Add/remove allocation lines
  and edit amounts; the remainder, status, and Save-enabled state update live.
- **Receipt entry (E)** — reach it from Transactions/Review. Add/remove line items; amount =
  qty × unit auto-calculates and the reconciliation status updates.
- **Reports → Analyst export (G)** — pick a prompt template (selection highlights), edit the
  checklist, and click **Copy prompt** for a copy confirmation.
- **Auth screens (F / F-qa)** — rendered outside the app frame. Use the top-right tabs to switch
  between the **Personal** variant and the **QA dev bypass** variant (red banner + bypass button).
  Try the login recovery-code toggle, show-passphrase, and the 3-step enrollment wizard with the
  recovery-codes acknowledgment gate.

Existing v1 screens (Sources, Review, Transactions, Reports, Settings) are stub panels marked
"unchanged from v1".

## Guardrails honored

- Approved terminology used verbatim; banned words (`envelope`, `give every dollar a job`,
  `available to spend`, `age of money`) never appear.
- Synthetic/redacted amounts only.
- No functional backend, no external/AI calls, no new dependencies.

## Files

- `index.html` — all screens and the auth stage.
- `mockup.css` — design tokens and layout adapted from `apps/web/src/styles.css`.
- `app.js` — visual-only interactions (vanilla JS).
