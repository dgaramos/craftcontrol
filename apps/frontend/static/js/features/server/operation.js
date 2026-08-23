/**
 * Operation lifecycle progress component (issue #192).
 *
 * Renders the staged progress of a server operation — completed, active,
 * pending, failed, and divergent stages with readable evidence and timestamps.
 * Survives navigation and reload via the /api/operations/latest endpoint and
 * an operation SSE stream.
 */

const STAGE_ORDER = ["review", "backup_verify", "prepare", "restart", "health_wait", "verify", "confirm"];
const STORAGE_KEY = "craftcontrol-operation-id";

export function createOperationFeature({ api, t, escapeHtml, formatDate, uiIcon, toast }) {
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
          try { localStorage.setItem(STORAGE_KEY, op.operation_id); } catch (_) { /* storage unavailable */ }
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
        try { localStorage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
      }
    } catch (_) { /* silently skip — the panel renders without an operation */ }
  }

  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

  async function loadFromStorage() {
    let storedId = null;
    try { storedId = localStorage.getItem(STORAGE_KEY); } catch (_) { /* storage unavailable */ }
    if (!storedId || !UUID_RE.test(storedId)) return;
    try {
      const response = await api(`/api/operations/${storedId}`);
      if (response.operation) currentOperation = response.operation;
    } catch (_) { /* silently skip */ }
  }

  // ------------------------------------------------------------------
  // Rendering
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

  function renderStageBar(stages) {
    return stages.map((record) => {
      const cls = stageClass(record);
      const label = stageLabel(record.stage);
      const timestamp = record.completed_at
        ? formatDate(record.completed_at * 1000)
        : record.started_at
          ? formatDate(record.started_at * 1000)
          : "";
      const title = timestamp ? `${label} · ${timestamp}` : label;
      return `<div class="op-stage op-stage-${escapeHtml(cls)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${uiIcon(cls === "completed" || cls === "skipped" ? "check" : cls === "failed" || cls === "divergent" ? "close" : "pending")}<span>${escapeHtml(label)}</span></div>`;
    }).join("");
  }

  function renderEvidence(evidence) {
    const entries = Object.entries(evidence || {});
    if (!entries.length) return "";
    const items = entries
      .filter(([, v]) => v !== null && v !== undefined && v !== "")
      .map(([k, v]) => `<div><dt>${escapeHtml(k.replace(/_/g, " "))}</dt><dd>${escapeHtml(String(v))}</dd></div>`)
      .join("");
    return items ? `<dl class="op-evidence">${items}</dl>` : "";
  }

  function activeStageMarkup(stages) {
    const running = stages.find((s) => s.result === "running");
    const failed = stages.find((s) => s.result === "failed");
    const divergent = stages.find((s) => s.result === "divergent");
    const active = running || failed || divergent;
    if (!active) return "";
    const label = stageLabel(active.stage);
    const started = active.started_at ? formatDate(active.started_at * 1000) : null;
    const errorLine = active.error ? `<p class="op-error">${uiIcon("warning")} ${escapeHtml(active.error)}</p>` : "";
    const timeLine = started ? `<small>${escapeHtml(started)}</small>` : "";
    return `<div class="op-active-stage"><strong>${escapeHtml(label)}</strong>${timeLine}${errorLine}${renderEvidence(active.evidence)}</div>`;
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

  function terminalMarkup(op) {
    if (!["confirmed", "failed", "divergent"].includes(op.state)) return "";
    const completed = op.completed_at ? `<small>${formatDate(op.completed_at * 1000)}</small>` : "";
    const errorLine = op.terminal_error ? `<p class="op-error">${uiIcon("warning")} ${escapeHtml(op.terminal_error)}</p>` : "";
    const observation = Object.entries(op.observation || {});
    const observationLine = observation.length
      ? `<dl class="op-evidence">${observation.map(([k, v]) => `<div><dt>${escapeHtml(k.replace(/_/g, " "))}</dt><dd>${escapeHtml(String(v))}</dd></div>`).join("")}</dl>`
      : "";
    const parentLink = op.parent_operation_id
      ? `<p class="op-parent-link"><small>${escapeHtml(t("opParentLink"))} <code class="op-parent-id"></code></small></p>`
      : "";
    const recoveryActions = ["failed", "divergent"].includes(op.state)
      ? `<div class="op-recovery-actions">
          <button class="secondary op-action" data-op-action="reconcile" title="${escapeHtml(t("opReconcileHelp"))}">${escapeHtml(t("opReconcile"))}</button>
          <button class="op-action" data-op-action="retry" title="${escapeHtml(t("opRetryHelp"))}">${escapeHtml(t("opRetry"))}</button>
        </div>`
      : "";
    return `<div class="op-terminal">${completed}${errorLine}${observationLine}${parentLink}${recoveryActions}</div>`;
  }

  function changesMarkup(op) {
    const entries = Object.entries(op.requested_changes || {});
    if (!entries.length) return "";
    return `<details class="op-changes"><summary>${t("opChanges")}</summary><ul>${entries.map(([k, v]) => `<li><strong>${escapeHtml(k)}</strong>: ${escapeHtml(String(v))}</li>`).join("")}</ul></details>`;
  }

  function renderOperation(op) {
    if (!op) return "";
    const stages = STAGE_ORDER.map((name) => {
      const record = (op.stages || []).find((s) => s.stage === name);
      return record || { stage: name, result: "pending", started_at: null, completed_at: null, evidence: {}, error: null };
    });
    const completed = stages.filter((s) => s.result === "completed" || s.result === "skipped").length;
    const stateClass = operationStateClass(op.state);
    const headline = operationHeadline(op);
    return `<section class="operation-progress-card block-panel op-state-${escapeHtml(stateClass)}">
  <div class="op-header">
    <span class="eyebrow">${escapeHtml(t("serverOperation"))}</span>
    <div class="op-headline">
      <h3>${escapeHtml(headline)}</h3>
      <span class="op-counter">${completed}/${STAGE_ORDER.length}</span>
    </div>
  </div>
  <div class="op-stage-bar" role="list" aria-label="${escapeHtml(t("opStages"))}">${renderStageBar(stages)}</div>
  ${activeStageMarkup(stages)}
  ${terminalMarkup(op)}
  ${changesMarkup(op)}
</section>`;
  }

  // ------------------------------------------------------------------
  // Recovery action handlers (issue #194)
  // ------------------------------------------------------------------

  async function handleReconcile(operationId) {
    const snapshotBefore = currentOperation;
    const response = await api(`/api/operations/${operationId}/reconcile`, { method: "POST" });
    if (response.operation && currentOperation === snapshotBefore) {
      currentOperation = response.operation;
      try { localStorage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
      if (onUpdate) onUpdate(currentOperation);
    }
  }

  async function handleRetry(operationId) {
    const snapshotBefore = currentOperation;
    const response = await api(`/api/operations/${operationId}/retry`, { method: "POST" });
    if (response.operation && currentOperation === snapshotBefore) {
      currentOperation = response.operation;
      try { localStorage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
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
    await loadFromStorage();
    if (!currentOperation) await loadLatest();
    connectStream();
  }

  function getOperation() {
    return currentOperation;
  }

  return { initialize, connectStream, setUpdateCallback, getOperation, renderOperation, bindRecoveryActions };
}
