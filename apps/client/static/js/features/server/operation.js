/**
 * Operation lifecycle progress component (issue #192).
 *
 * Renders the staged progress of a server operation — completed, active,
 * pending, failed, and divergent stages with readable evidence and timestamps.
 * Survives navigation and reload via the /api/operations/latest endpoint and
 * an operation SSE stream.
 *
 * renderOperation returns a DocumentFragment, not an HTML string. API-derived
 * values are set exclusively via textContent; uiIcon() output is injected into
 * dedicated icon slots via innerHTML as trusted static markup (issue #219).
 */

const STAGE_ORDER = ["review", "backup_verify", "prepare", "restart", "health_wait", "verify", "confirm"];
const STORAGE_KEY = "craftcontrol-operation-id";

function operationDate(value, formatDate) {
  return value ? formatDate(value) : "";
}

function displayOperationValue(value, formatDate, key = "") {
  if (value === null || value === undefined) return "";
  const formatTimestamp = (property, candidate) => {
    const normalizedProperty = String(property).replace(/([a-z])([A-Z])/g, "$1_$2").toLowerCase();
    if (!/(?:_at|timestamp|time|date)$/.test(normalizedProperty) || candidate === null || typeof candidate === "object") return candidate;
    const formatted = formatDate(candidate);
    return formatted === "—" ? candidate : formatted;
  };
  if (typeof value !== "object") return String(formatTimestamp(key, value));
  return "";
}

export function createOperationFeature({ api, t, formatDate, uiIcon, toast, storage = localStorage }) {
  let currentOperation = null;
  let eventSource = null;
  let onUpdate = null;

  // ------------------------------------------------------------------
  // SSE subscription to /api/operations/stream
  // ------------------------------------------------------------------

  function connectStream(lastEventId = 0) {
    if (eventSource) return;
    if (typeof EventSource === "undefined") return;
    const url = "/api/operations/stream";
    eventSource = new EventSource(url);
    eventSource.addEventListener("operation", (message) => {
      try {
        const op = JSON.parse(message.data);
        if (op && op.operation_id) {
          currentOperation = op;
          try { storage.setItem(STORAGE_KEY, op.operation_id); } catch (_) { /* storage unavailable */ }
          if (onUpdate) onUpdate(op);
        }
      } catch (_) { /* ignore malformed SSE payload */ }
    });
    eventSource.onopen = async () => {
      // Re-fetch on every (re)connection to recover events missed during a gap.
      await loadLatest();
      if (currentOperation && onUpdate) onUpdate(currentOperation);
    };
    eventSource.onerror = () => {
      // EventSource reconnects automatically; no explicit handling needed.
    };
  }

  // ------------------------------------------------------------------
  // API helpers
  // ------------------------------------------------------------------

  async function loadLatest() {
    const snapshotBefore = currentOperation;
    try {
      const response = await api("/api/operations/latest");
      // Only apply the REST response if no SSE event updated currentOperation
      // while the request was in-flight, preserving event-driven freshness.
      if (response.operation && currentOperation === snapshotBefore) {
        currentOperation = response.operation;
        try { storage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
      } else if (!response.operation && currentOperation === snapshotBefore) {
        currentOperation = null;
        try { storage.removeItem(STORAGE_KEY); } catch (_) { /* storage unavailable */ }
      }
      return true;
    } catch (_) {
      return false;
    }
  }

  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  async function loadFromStorage() {
    let storedId = null;
    try { storedId = storage.getItem(STORAGE_KEY); } catch (_) { /* storage unavailable */ }
    if (!storedId || !UUID_RE.test(storedId)) return;
    try {
      const response = await api(`/api/operations/${storedId}`);
      if (response.operation) currentOperation = response.operation;
    } catch (_) { /* silently skip */ }
  }

  // ------------------------------------------------------------------
  // Rendering helpers — all return DOM nodes, never HTML strings.
  // API-derived text is always set via textContent.
  // uiIcon() output is injected into dedicated icon slots via innerHTML
  // because it is trusted static markup, not API-derived content.
  // ------------------------------------------------------------------

  function stageLabel(stageName) {
    const key = `opStage_${stageName}`;
    return t(key) || stageName;
  }

  function stageClass(record) {
    if (!record) return "pending";
    if (record.result === "running") return "running";
    if (record.result === "completed") return "completed";
    if (record.result === "skipped") return "skipped";
    if (record.result === "failed") return "failed";
    if (record.result === "divergent") return "divergent";
    return "pending";
  }

  /**
   * Appends one .op-stage child per record into the given container element.
   */
  function renderStageBar(stages, container) {
    stages.forEach((record) => {
      const cls = stageClass(record);
      const label = stageLabel(record.stage);
      const timestamp = operationDate(record.completed_at || record.started_at, formatDate);
      const title = timestamp ? `${label} · ${timestamp}` : label;

      const div = document.createElement("div");
      div.className = `op-stage op-stage-${cls}`;
      div.title = title;
      div.setAttribute("aria-label", title);

      const iconName =
        cls === "completed" || cls === "skipped" ? "check"
          : cls === "failed" || cls === "divergent" ? "close"
            : "pending";
      // icon slot: trusted static SVG markup from uiIcon()
      const iconSlot = document.createElement("span");
      iconSlot.innerHTML = uiIcon(iconName);
      div.appendChild(iconSlot);

      const span = document.createElement("span");
      span.textContent = label;
      div.appendChild(span);

      container.appendChild(div);
    });
  }

  function displayFieldName(key) {
    return String(key).replace(/_/g, " ");
  }

  /** Appends scalar or structured API data without serialising it as JSON. */
  function appendOperationValue(container, value, key = "") {
    if (value === null || value === undefined || value === "") return;
    if (typeof value !== "object") {
      container.textContent = displayOperationValue(value, formatDate, key);
      return;
    }

    const entries = Array.isArray(value) ? value.map((item, index) => [index + 1, item]) : Object.entries(value);
    if (!entries.length) {
      container.textContent = "—";
      return;
    }

    const details = document.createElement("details");
    details.className = "op-structured-value";
    const summary = document.createElement("summary");
    summary.textContent = Array.isArray(value) ? t("opItems") : t("opFields");
    details.appendChild(summary);

    const list = document.createElement("dl");
    list.className = "op-evidence op-evidence-nested";
    entries.forEach(([nestedKey, nestedValue]) => {
      const item = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = displayFieldName(nestedKey);
      const dd = document.createElement("dd");
      appendOperationValue(dd, nestedValue, nestedKey);
      item.append(dt, dd);
      list.appendChild(item);
    });
    details.appendChild(list);
    container.appendChild(details);
  }

  /**
   * Builds a collapsible evidence section from an evidence object.
   * Returns null when the object is empty or has no displayable entries.
   */
  function renderEvidence(evidence, label = t("opEvidence")) {
    const entries = Object.entries(evidence || {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
    if (!entries.length) return null;

    const details = document.createElement("details");
    details.className = "op-evidence-details";
    const summary = document.createElement("summary");
    summary.textContent = label;
    details.appendChild(summary);

    const dl = document.createElement("dl");
    dl.className = "op-evidence";

    entries.forEach(([k, v]) => {
      const item = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = displayFieldName(k);
      const dd = document.createElement("dd");
      appendOperationValue(dd, v, k);
      item.append(dt, dd);
      dl.appendChild(item);
    });

    details.appendChild(dl);
    return details;
  }

  /**
   * Returns a <div class="op-active-stage"> for the currently running,
   * failed, or divergent stage, or null when no such stage exists.
   * API-derived stage error and evidence are set via textContent / renderEvidence.
   */
  function activeStageMarkup(stages) {
    const running = stages.find((s) => s.result === "running");
    const failed = stages.find((s) => s.result === "failed");
    const divergent = stages.find((s) => s.result === "divergent");
    const active = running || failed || divergent;
    if (!active) return null;

    const label = stageLabel(active.stage);
    const started = operationDate(active.started_at, formatDate) || null;

    const div = document.createElement("div");
    div.className = "op-active-stage";

    const strong = document.createElement("strong");
    strong.textContent = label;
    div.appendChild(strong);

    if (started) {
      const small = document.createElement("small");
      small.textContent = started;
      div.appendChild(small);
    }

    if (active.error) {
      const p = document.createElement("p");
      p.className = "op-error";
      // icon slot: trusted static SVG markup
      const iconSlot = document.createElement("span");
      iconSlot.innerHTML = uiIcon("warning");
      p.appendChild(iconSlot);
      // API-derived error text via textContent
      const errorText = document.createElement("span");
      errorText.className = "op-error-text";
      errorText.textContent = active.error;
      p.appendChild(errorText);
      div.appendChild(p);
    }

    const evidenceNode = renderEvidence(active.evidence);
    if (evidenceNode) div.appendChild(evidenceNode);

    return div;
  }

  function operationStateClass(state) {
    if (state === "confirmed") return "confirmed";
    if (state === "failed") return "failed";
    if (state === "divergent") return "divergent";
    if (state === "running") return "running";
    return "pending";
  }

  function operationHeadline(op) {
    const stateKey = `opState_${op.state}`;
    return t(stateKey) || op.state;
  }

  /**
   * Returns a <div class="op-terminal"> for confirmed, failed, or divergent
   * operations, or null for still-running ones.
   * API-derived terminal_error, observation, and parent_operation_id are
   * set via textContent; recovery button labels come from t() (i18n, not API).
   */
  function terminalMarkup(op) {
    if (!["confirmed", "failed", "divergent"].includes(op.state)) return null;

    const div = document.createElement("div");
    div.className = "op-terminal";

    if (op.completed_at) {
      const small = document.createElement("small");
      small.textContent = operationDate(op.completed_at, formatDate);
      div.appendChild(small);
    }

    if (op.terminal_error) {
      const p = document.createElement("p");
      p.className = "op-error";
      // icon slot: trusted static SVG markup
      const iconSlot = document.createElement("span");
      iconSlot.innerHTML = uiIcon("warning");
      p.appendChild(iconSlot);
      // API-derived error via textContent
      const errorSpan = document.createElement("span");
      errorSpan.className = "op-error-text";
      errorSpan.textContent = op.terminal_error;
      p.appendChild(errorSpan);
      div.appendChild(p);
    }

    const reconciliation = op.observation?.reconciliation_result;
    if (reconciliation?.state) {
      const status = document.createElement("p");
      status.className = `op-reconciliation op-reconciliation-${reconciliation.state}`;
      const label = document.createElement("strong");
      label.textContent = t("opObservedState");
      status.appendChild(label);
      status.appendChild(document.createTextNode(`: ${t(`opReconciliation_${reconciliation.state}`) || reconciliation.state}`));
      div.appendChild(status);
    }

    const observation = Object.fromEntries(Object.entries(op.observation || {}).filter(([key]) => key !== "reconciliation_result"));
    const observationNode = renderEvidence(observation, t("opObservation"));
    if (observationNode) div.appendChild(observationNode);

    if (op.parent_operation_id) {
      const p = document.createElement("p");
      p.className = "op-parent-link";
      const small = document.createElement("small");
      // i18n label via textContent (not API-derived)
      small.appendChild(document.createTextNode(t("opParentLink") + " "));
      const code = document.createElement("code");
      code.className = "op-parent-id";
      // parent_operation_id is set later by bindRecoveryActions via textContent
      small.appendChild(code);
      p.appendChild(small);
      div.appendChild(p);
    }

    if (["failed", "divergent"].includes(op.state)) {
      const actionsDiv = document.createElement("div");
      actionsDiv.className = "op-recovery-actions";

      const reconcileBtn = document.createElement("button");
      reconcileBtn.className = "secondary op-action";
      reconcileBtn.dataset.opAction = "reconcile";
      reconcileBtn.title = t("opReconcileHelp");
      reconcileBtn.textContent = t("opReconcile");
      actionsDiv.appendChild(reconcileBtn);

      const retryBtn = document.createElement("button");
      retryBtn.className = "op-action";
      retryBtn.dataset.opAction = "retry";
      retryBtn.title = t("opRetryHelp");
      retryBtn.textContent = t("opRetry");
      actionsDiv.appendChild(retryBtn);

      div.appendChild(actionsDiv);
    }

    return div;
  }

  /**
   * Returns a <details class="op-changes"> element listing the requested
   * changes, or null when there are none.
   * Change keys and values are set via textContent.
   */
  function changesMarkup(op) {
    const entries = Object.entries(op.requested_changes || {});
    if (!entries.length) return null;

    const details = document.createElement("details");
    details.className = "op-changes";

    const summary = document.createElement("summary");
    summary.textContent = t("opChanges");
    details.appendChild(summary);

    const ul = document.createElement("ul");
    entries.forEach(([k, v]) => {
      const li = document.createElement("li");
      const strong = document.createElement("strong");
      strong.textContent = k;
      li.appendChild(strong);
      li.appendChild(document.createTextNode(": "));
      const value = document.createElement("span");
      appendOperationValue(value, v, k);
      li.appendChild(value);
      ul.appendChild(li);
    });
    details.appendChild(ul);

    return details;
  }

  /**
   * Returns a DocumentFragment containing the full operation progress card,
   * or null when op is falsy.
   *
   * Callers must insert the fragment into the DOM directly (e.g. via
   * container.replaceChildren(fragment)) rather than serialising it to HTML.
   */
  function renderOperation(op) {
    if (!op) return null;

    const stages = STAGE_ORDER.map((name) => {
      const record = (op.stages || []).find((s) => s.stage === name);
      return record || { stage: name, result: "pending", started_at: null, completed_at: null, evidence: {}, error: null };
    });
    const completed = stages.filter((s) => s.result === "completed" || s.result === "skipped").length;
    const stateClass = operationStateClass(op.state);
    const headline = operationHeadline(op);

    const frag = document.createDocumentFragment();

    const section = document.createElement("section");
    section.className = `operation-progress-card block-panel op-state-${stateClass}`;

    // Header
    const header = document.createElement("div");
    header.className = "op-header";

    const eyebrow = document.createElement("span");
    eyebrow.className = "eyebrow";
    eyebrow.textContent = t("serverOperation");
    header.appendChild(eyebrow);

    const headlineDiv = document.createElement("div");
    headlineDiv.className = "op-headline";

    const h3 = document.createElement("h3");
    h3.textContent = headline;
    headlineDiv.appendChild(h3);

    const counter = document.createElement("span");
    counter.className = "op-counter";
    counter.textContent = `${completed}/${STAGE_ORDER.length}`;
    headlineDiv.appendChild(counter);

    header.appendChild(headlineDiv);
    section.appendChild(header);

    // Stage bar
    const stageBar = document.createElement("div");
    stageBar.className = "op-stage-bar";
    stageBar.setAttribute("role", "list");
    stageBar.setAttribute("aria-label", t("opStages"));
    renderStageBar(stages, stageBar);
    section.appendChild(stageBar);

    // Active stage
    const activeNode = activeStageMarkup(stages);
    if (activeNode) section.appendChild(activeNode);

    // Terminal summary
    const terminalNode = terminalMarkup(op);
    if (terminalNode) section.appendChild(terminalNode);

    // Requested changes
    const changesNode = changesMarkup(op);
    if (changesNode) section.appendChild(changesNode);

    frag.appendChild(section);
    return frag;
  }

  // ------------------------------------------------------------------
  // Recovery action handlers (issue #194)
  // ------------------------------------------------------------------

  async function handleReconcile(operationId) {
    const snapshotBefore = currentOperation;
    const response = await api(`/api/operations/${operationId}/reconcile`, { method: "POST" });
    if (response.operation && currentOperation === snapshotBefore) {
      currentOperation = response.operation;
      try { storage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
      if (onUpdate) onUpdate(currentOperation);
    }
  }

  async function handleRetry(operationId) {
    const snapshotBefore = currentOperation;
    const response = await api(`/api/operations/${operationId}/retry`, { method: "POST" });
    if (response.operation && currentOperation === snapshotBefore) {
      currentOperation = response.operation;
      try { storage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
      if (onUpdate) onUpdate(currentOperation);
    }
  }

  // in-flight guard keyed by operation_id; prevents concurrent reconcile+retry
  const _inflight = new Set();

  function bindRecoveryActions(container) {
    if (!container) return;
    const op = currentOperation;
    if (!op) return;

    // Set parent_operation_id via textContent — never via innerHTML interpolation
    const parentEl = container.querySelector(".op-parent-id");
    if (parentEl && op.parent_operation_id) {
      parentEl.textContent = op.parent_operation_id.slice(0, 8);
    }

    container.querySelectorAll("[data-op-action]").forEach((button) => {
      button.onclick = async () => {
        const opId = op.operation_id;
        if (_inflight.has(opId)) return;
        _inflight.add(opId);
        container.querySelectorAll("[data-op-action]").forEach((b) => { b.disabled = true; });
        try {
          const action = button.dataset.opAction;
          if (action === "reconcile") await handleReconcile(opId);
          else if (action === "retry") await handleRetry(opId);
        } catch (err) {
          const isConflict = err && (err.status === 409 || (typeof err.message === "string" && err.message.includes("409")));
          if (toast) toast(isConflict ? t("opRetryConflict") : (err && err.message) || t("opRetry"), true);
        } finally {
          _inflight.delete(opId);
          container.querySelectorAll("[data-op-action]").forEach((b) => { b.disabled = false; });
        }
      };
    });
  }

  // ------------------------------------------------------------------
  // Public interface
  // ------------------------------------------------------------------

  function setUpdateCallback(callback) {
    onUpdate = callback;
  }

  async function initialize() {
    // The API is authoritative. Browser storage is only an offline fallback.
    const loadedLatest = await loadLatest();
    if (!loadedLatest && !currentOperation) await loadFromStorage();
    connectStream();
  }

  function getOperation() {
    return currentOperation;
  }

  return { initialize, connectStream, setUpdateCallback, getOperation, renderOperation, bindRecoveryActions };
}
