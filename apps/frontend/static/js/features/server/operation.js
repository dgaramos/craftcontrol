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

export function createOperationFeature({ api, t, escapeHtml, formatDate, uiIcon }) {
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
    eventSource.onerror = () => {
      // EventSource reconnects automatically; no explicit handling needed.
    };
  }

  // ------------------------------------------------------------------
  // API helpers
  // ------------------------------------------------------------------

  async function loadLatest() {
    try {
      const response = await api("/api/operations/latest");
      if (response.operation) {
        currentOperation = response.operation;
        try { localStorage.setItem(STORAGE_KEY, response.operation.operation_id); } catch (_) { /* storage unavailable */ }
      }
    } catch (_) { /* silently skip — the panel renders without an operation */ }
  }

  async function loadFromStorage() {
    let storedId = null;
    try { storedId = localStorage.getItem(STORAGE_KEY); } catch (_) { /* storage unavailable */ }
    if (!storedId) return;
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
      return `<div class="op-stage op-stage-${escapeHtml(cls)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${uiIcon(cls === "completed" || cls === "skipped" ? "check" : cls === "failed" ? "close" : "pending")}<span>${escapeHtml(label)}</span></div>`;
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
    const active = running || failed;
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
    return `<div class="op-terminal">${completed}${errorLine}${observationLine}</div>`;
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

  return { initialize, connectStream, setUpdateCallback, getOperation, renderOperation };
}
