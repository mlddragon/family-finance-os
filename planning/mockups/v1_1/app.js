/*
 * Family Finance OS — v1.1 interactive mockups
 * Visual-only vanilla JS. No fetch, no backend, no dependencies.
 * Every interaction below changes only the on-screen display.
 */
(function () {
  "use strict";

  var CATEGORIES = [
    "Groceries",
    "Household",
    "Personal care",
    "Auto & fuel",
    "Dining",
    "Utilities",
    "Buffer",
  ];

  function money(n) {
    var sign = n < 0 ? "-" : "";
    var abs = Math.abs(n).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return sign + "$" + abs;
  }

  // ---------------------------------------------------------------------------
  // Navigation: sidebar + contextual buttons switch the visible screen.
  // Auth screens render outside the app frame.
  // ---------------------------------------------------------------------------
  var appShell = document.getElementById("app-shell");
  var authStage = document.getElementById("auth-stage");
  var sidebar = document.getElementById("sidebar");

  function setScreen(key) {
    if (key === "auth") {
      appShell.hidden = true;
      authStage.hidden = false;
      return;
    }
    appShell.hidden = false;
    authStage.hidden = true;

    document.querySelectorAll(".screen").forEach(function (section) {
      section.classList.toggle("active", section.getAttribute("data-screen") === key);
    });

    // Keep sidebar highlight on the closest primary destination.
    var primary = { split: "transactions", receipt: "transactions", export: "reports" };
    var navKey = primary[key] || key;
    sidebar.querySelectorAll("a[data-nav]").forEach(function (link) {
      if (link.getAttribute("data-nav") === navKey) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });

    var content = document.querySelector(".content");
    if (content) content.scrollTop = 0;
    window.scrollTo(0, 0);
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-nav]");
    if (!trigger) return;
    event.preventDefault();
    setScreen(trigger.getAttribute("data-nav"));
  });

  // ---------------------------------------------------------------------------
  // Screen A: Home — provisional exposure toggle recomputes the headline.
  // ---------------------------------------------------------------------------
  (function home() {
    var toggle = document.getElementById("provisional-toggle");
    if (!toggle) return;

    var BASE = 3412.58;
    var PROVISIONAL = 1842.0;
    var amount = document.getElementById("spendable-amount");
    var label = document.getElementById("spendable-label");
    var note = document.getElementById("spendable-note");
    var op = document.getElementById("prov-op");
    var term = document.getElementById("prov-term");

    function render() {
      if (toggle.checked) {
        amount.textContent = money(BASE - PROVISIONAL);
        amount.classList.add("provisional");
        label.textContent = "Spendable balance (provisional)";
        op.hidden = false;
        term.hidden = false;
        note.textContent =
          "Provisional means: outflows seen in imports but not yet reviewed. Reviewing them in Review moves them out of provisional.";
      } else {
        amount.textContent = money(BASE);
        amount.classList.remove("provisional");
        label.textContent = "Spendable balance";
        op.hidden = true;
        term.hidden = true;
        note.textContent =
          "Excludes " + money(PROVISIONAL) + " provisional exposure (unreviewed outflows).";
      }
    }
    toggle.addEventListener("change", render);
    render();
  })();

  // ---------------------------------------------------------------------------
  // Screen B: Funds — overcommit warning demo toggle.
  // ---------------------------------------------------------------------------
  (function funds() {
    var btn = document.getElementById("overcommit-demo");
    if (!btn) return;
    var band = document.getElementById("overcommit-band");
    var commitTotal = document.getElementById("commit-total");
    var fitMetric = document.getElementById("commit-fit");
    var on = false;

    btn.addEventListener("click", function () {
      on = !on;
      band.hidden = !on;
      if (on) {
        commitTotal.textContent = "$3,110.00";
        fitMetric.classList.remove("ok");
        fitMetric.classList.add("danger");
        fitMetric.innerHTML =
          "<span>Overcommitted</span><strong>-$310.00</strong><p>Commitments exceed funding</p>";
        btn.textContent = "Reset funding state";
      } else {
        commitTotal.textContent = "$2,640.00";
        fitMetric.classList.remove("danger");
        fitMetric.classList.add("ok");
        fitMetric.innerHTML =
          "<span>Uncommitted</span><strong>$160.00</strong><p>OK: commitments fit funding</p>";
        btn.textContent = "Demo overcommit warning";
      }
    });
  })();

  // ---------------------------------------------------------------------------
  // Screen C: Dashboard — net worth "include estimates" toggle.
  // ---------------------------------------------------------------------------
  (function dashboard() {
    var toggle = document.getElementById("networth-toggle");
    if (!toggle) return;
    var band = document.getElementById("networth-band");
    toggle.addEventListener("change", function () {
      band.hidden = !toggle.checked;
    });
  })();

  // ---------------------------------------------------------------------------
  // Screen D: Split editor — add/remove rows, live remainder (display only).
  // ---------------------------------------------------------------------------
  (function split() {
    var container = document.getElementById("split-rows");
    if (!container) return;
    var TOTAL = parseFloat(container.getAttribute("data-total"));
    var allocatedEl = document.getElementById("split-allocated");
    var remainderEl = document.getElementById("split-remainder");
    var statusEl = document.getElementById("split-status");
    var lineCountEl = document.getElementById("split-line-count");
    var saveBtn = document.getElementById("split-save");

    var seed = [
      { cat: "Groceries", amt: "120.00", note: "weekly food" },
      { cat: "Household", amt: "49.45", note: "paper goods" },
      { cat: "Personal care", amt: "20.00", note: "" },
    ];

    function categoryOptions(selected) {
      return CATEGORIES.map(function (c) {
        return '<option value="' + c + '"' + (c === selected ? " selected" : "") + ">" + c + "</option>";
      }).join("");
    }

    function addRow(data) {
      data = data || { cat: "Groceries", amt: "0.00", note: "" };
      var row = document.createElement("div");
      row.className = "alloc-row";
      row.innerHTML =
        '<span class="alloc-index"></span>' +
        '<select aria-label="Category or pool">' + categoryOptions(data.cat) + "</select>" +
        '<input type="text" inputmode="decimal" class="amt" aria-label="Amount" value="-' + data.amt + '" />' +
        '<input type="text" aria-label="Note" placeholder="note" value="' + data.note + '" />' +
        '<button type="button" class="remove-row">Remove</button>';
      container.appendChild(row);
      row.querySelector(".amt").addEventListener("input", recalc);
      row.querySelector(".remove-row").addEventListener("click", function () {
        row.remove();
        recalc();
      });
      recalc();
    }

    function parseAmt(v) {
      var n = parseFloat(String(v).replace(/[^0-9.\-]/g, ""));
      return isNaN(n) ? 0 : Math.abs(n);
    }

    function recalc() {
      var rows = container.querySelectorAll(".alloc-row");
      var sum = 0;
      rows.forEach(function (row, i) {
        row.querySelector(".alloc-index").textContent = i + 1;
        sum += parseAmt(row.querySelector(".amt").value);
      });
      var remainder = TOTAL - sum;
      allocatedEl.textContent = money(-sum);
      lineCountEl.textContent = rows.length;

      var balanced = Math.abs(remainder) < 0.005;
      var enoughLines = rows.length >= 2;

      remainderEl.classList.remove("danger-text", "ok-text");
      if (balanced) {
        remainderEl.textContent = money(0);
        remainderEl.classList.add("ok-text");
        statusEl.textContent = enoughLines
          ? "Balanced — ready to save"
          : "Add a second line — a 1-line split is just a categorization";
        statusEl.className = "remainder-status " + (enoughLines ? "ok-text" : "warn-text");
      } else if (remainder > 0) {
        remainderEl.textContent = money(remainder);
        remainderEl.classList.add("danger-text");
        statusEl.textContent = "Remainder " + money(remainder) + " — allocations must sum to the transaction amount";
        statusEl.className = "remainder-status danger-text";
      } else {
        remainderEl.textContent = money(remainder);
        remainderEl.classList.add("danger-text");
        statusEl.textContent = "Over by " + money(-remainder) + " — reduce an allocation";
        statusEl.className = "remainder-status danger-text";
      }
      saveBtn.disabled = !(balanced && enoughLines);
    }

    document.getElementById("split-add").addEventListener("click", function () {
      addRow();
    });

    seed.forEach(addRow);
  })();

  // ---------------------------------------------------------------------------
  // Screen E: Receipt entry — add/remove items, qty*unit auto, totals.
  // ---------------------------------------------------------------------------
  (function receipt() {
    var container = document.getElementById("receipt-rows");
    if (!container) return;
    var RECEIPT_TOTAL = 189.45;
    var itemsEl = document.getElementById("receipt-items");
    var unaccountedEl = document.getElementById("receipt-unaccounted");
    var unaccountedLabel = document.getElementById("receipt-unaccounted-label");
    var statusEl = document.getElementById("receipt-status");

    var seed = [
      { desc: "Bananas", qty: "2", unit: "0.59", cat: "Groceries" },
      { desc: "Paper towels", qty: "1", unit: "8.99", cat: "Household" },
      { desc: "Shampoo", qty: "1", unit: "6.49", cat: "Personal care" },
    ];

    function categoryOptions(selected) {
      return CATEGORIES.map(function (c) {
        return '<option value="' + c + '"' + (c === selected ? " selected" : "") + ">" + c + "</option>";
      }).join("");
    }

    function addRow(data) {
      data = data || { desc: "", qty: "1", unit: "0.00", cat: "Groceries" };
      var row = document.createElement("div");
      row.className = "alloc-row receipt-row";
      row.innerHTML =
        '<span class="alloc-index"></span>' +
        '<input type="text" aria-label="Description" placeholder="item" value="' + data.desc + '" />' +
        '<input type="text" inputmode="numeric" class="qty" aria-label="Quantity" value="' + data.qty + '" />' +
        '<input type="text" inputmode="decimal" class="unit" aria-label="Unit price" value="$' + data.unit + '" />' +
        '<input type="text" class="amount" aria-label="Amount" readonly />' +
        '<select aria-label="Category">' + categoryOptions(data.cat) + "</select>" +
        '<button type="button" class="remove-row">Remove</button>';
      container.appendChild(row);
      row.querySelector(".qty").addEventListener("input", recalc);
      row.querySelector(".unit").addEventListener("input", recalc);
      row.querySelector(".remove-row").addEventListener("click", function () {
        row.remove();
        recalc();
      });
      recalc();
    }

    function num(v) {
      var n = parseFloat(String(v).replace(/[^0-9.\-]/g, ""));
      return isNaN(n) ? 0 : n;
    }

    function recalc() {
      var rows = container.querySelectorAll(".receipt-row");
      var total = 0;
      rows.forEach(function (row, i) {
        row.querySelector(".alloc-index").textContent = i + 1;
        var line = num(row.querySelector(".qty").value) * num(row.querySelector(".unit").value);
        row.querySelector(".amount").value = money(line);
        total += line;
      });
      itemsEl.textContent = money(total);

      var diff = RECEIPT_TOTAL - total;
      statusEl.classList.remove("ok-text", "warn-text", "danger-text");
      if (Math.abs(diff) < 0.005) {
        unaccountedLabel.textContent = "Reconciled";
        unaccountedEl.textContent = money(0);
        statusEl.textContent = "Reconciled — items match the receipt total";
        statusEl.classList.add("ok-text");
      } else if (diff < 0) {
        unaccountedLabel.textContent = "Over receipt total";
        unaccountedEl.textContent = money(-diff);
        statusEl.textContent = "Over receipt total by " + money(-diff) + " — check quantities";
        statusEl.classList.add("warn-text");
      } else {
        unaccountedLabel.textContent = "Unaccounted";
        unaccountedEl.textContent = money(diff);
        statusEl.textContent = "Optional — itemize as much as you want";
        statusEl.classList.add("warn-text");
      }
    }

    document.getElementById("receipt-add").addEventListener("click", function () {
      addRow();
    });

    seed.forEach(addRow);
  })();

  // ---------------------------------------------------------------------------
  // Screen G: Analyst export — prompt picker selection + copy confirmation.
  // ---------------------------------------------------------------------------
  (function analystExport() {
    var picker = document.getElementById("prompt-picker");
    if (!picker) return;
    var textEl = document.getElementById("prompt-text");
    var copyBtn = document.getElementById("copy-prompt");
    var toast = document.getElementById("copy-toast");

    var PROMPTS = {
      monthly:
        "Using the attached export pack, give a monthly spending review by category. Call out the largest changes versus the prior month and flag anything marked provisional.",
      cashflow:
        "Using the attached export pack, summarize net cashflow and savings rate for the period. Note any months marked provisional and do not infer beyond the provided data.",
      goal:
        "Using the attached export pack, report progress toward each reserved goal target. State remaining-to-target and whether the current pace meets any target dates provided.",
      custom: "Write your own prompt here. The export pack is attached as .json + .md.",
    };

    picker.addEventListener("change", function (event) {
      var value = event.target.value;
      textEl.textContent = PROMPTS[value] || "";
      picker.querySelectorAll(".prompt-option").forEach(function (opt) {
        opt.classList.toggle("selected", opt.getAttribute("data-prompt") === value);
      });
    });

    copyBtn.addEventListener("click", function () {
      var text = textEl.textContent;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(function () {});
      }
      toast.classList.add("show");
      setTimeout(function () {
        toast.classList.remove("show");
      }, 1600);
    });
  })();

  // ---------------------------------------------------------------------------
  // Screen F: Auth — variant tabs, recovery mode, show passphrase, wizard steps.
  // ---------------------------------------------------------------------------
  (function auth() {
    var tabs = document.querySelectorAll("[data-authmode]");
    var qaBanner = document.getElementById("auth-qa-banner");
    var qaBypass = document.getElementById("qa-bypass");
    var brand = document.getElementById("auth-brand-name");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var mode = tab.getAttribute("data-authmode");
        tabs.forEach(function (t) {
          t.setAttribute("aria-pressed", t === tab ? "true" : "false");
        });
        var qa = mode === "qa";
        qaBanner.hidden = !qa;
        qaBypass.hidden = !qa;
        brand.textContent = qa ? "Family Finance OS (QA)" : "Family Finance OS";
      });
    });

    var recoveryLink = document.getElementById("recovery-link");
    var totpField = document.getElementById("totp-field");
    var recoveryField = document.getElementById("recovery-field");
    var recoveryMode = false;
    if (recoveryLink) {
      recoveryLink.addEventListener("click", function () {
        recoveryMode = !recoveryMode;
        totpField.style.display = recoveryMode ? "none" : "grid";
        recoveryField.style.display = recoveryMode ? "grid" : "none";
        recoveryLink.textContent = recoveryMode ? "Use authenticator code" : "Use a recovery code";
      });
    }

    var showBtn = document.getElementById("toggle-passphrase");
    if (showBtn) {
      showBtn.addEventListener("click", function () {
        var input = showBtn.parentElement.querySelector('input[type="password"], input[type="text"]');
        if (!input) return;
        var showing = input.type === "text";
        input.type = showing ? "password" : "text";
        showBtn.textContent = showing ? "Show passphrase" : "Hide passphrase";
      });
    }

    // Enrollment wizard (visual step buttons only).
    var steps = document.querySelectorAll("#wizard-steps .step");
    var panels = document.querySelectorAll("[data-wizard-panel]");
    var stepLabel = document.getElementById("wizard-step-label");
    var backBtn = document.getElementById("wizard-back");
    var nextBtn = document.getElementById("wizard-next");
    var ack = document.getElementById("recovery-ack");
    if (!nextBtn) return;

    var LABELS = {
      1: "Step 1 of 3: Set a passphrase",
      2: "Step 2 of 3: Set up authenticator",
      3: "Step 3 of 3: Recovery codes",
    };
    var current = 1;

    function renderWizard() {
      panels.forEach(function (p) {
        p.hidden = p.getAttribute("data-wizard-panel") !== String(current);
      });
      steps.forEach(function (s) {
        var n = Number(s.getAttribute("data-step"));
        s.classList.toggle("done", n <= current);
      });
      stepLabel.textContent = LABELS[current];
      backBtn.disabled = current === 1;
      if (current < 3) {
        nextBtn.textContent = "Confirm & continue";
        nextBtn.disabled = false;
      } else {
        nextBtn.textContent = "Finish setup";
        nextBtn.disabled = !(ack && ack.checked);
      }
    }

    if (ack) {
      ack.addEventListener("change", renderWizard);
    }
    backBtn.addEventListener("click", function () {
      if (current > 1) current--;
      renderWizard();
    });
    nextBtn.addEventListener("click", function () {
      if (current < 3) {
        current++;
        renderWizard();
      } else if (ack && ack.checked) {
        nextBtn.textContent = "Setup complete";
        nextBtn.disabled = true;
      }
    });

    renderWizard();
  })();
})();
