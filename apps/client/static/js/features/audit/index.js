/**
 * Audit history panel (issue #268).
 *
 * Owner-only panel that shows a paginated, filtered list of audit records
 * sourced from GET /api/audit.  No browser polling — data is fetched on
 * panel open and whenever the user applies filters or changes the page.
 */

export function createAuditFeature({ state, content, t, api, $, escapeHtml, toast, formatDate, uiIcon }) {
  // Local filter/pagination state — lives entirely inside this closure.
  let page = 1;
  let actorFilter = "";
  let actionFilter = "";
  // Incremented on every render call; response handlers check it to discard stale results.
  let renderGeneration = 0;

  // ------------------------------------------------------------------
  // Rendering helpers
  // ------------------------------------------------------------------

  function outcomeClass(result) {
    if (result === "success") return "audit-outcome--success";
    if (result === "denied" || result === "failure") return "audit-outcome--failure";
    return "audit-outcome--neutral";
  }

  function renderRecord(rec) {
    const date = rec.occurred_at ? formatDate(rec.occurred_at) : "—";
    const actor = rec.actor ? escapeHtml(rec.actor) : "—";
    const target = rec.target ? escapeHtml(rec.target) : "—";
    const action = escapeHtml(rec.action);
    const result = escapeHtml(rec.result);
    return `
      <tr>
        <td>${actor}</td>
        <td><span class="audit-action-code">${action}</span></td>
        <td><span class="audit-target" title="${target}">${target}</span></td>
        <td><span class="audit-outcome ${outcomeClass(rec.result)}">${result}</span></td>
        <td class="audit-date">${date}</td>
      </tr>`;
  }

  function renderFilters() {
    return `
      <div class="audit-filters">
        <label>
          ${escapeHtml(t("auditActor"))}
          <input id="audit-actor-input" type="text" value="${escapeHtml(actorFilter)}" placeholder="${escapeHtml(t("auditFilterAll"))}" />
        </label>
        <label>
          ${escapeHtml(t("auditAction"))}
          <input id="audit-action-input" type="text" value="${escapeHtml(actionFilter)}" placeholder="${escapeHtml(t("auditFilterAll"))}" />
        </label>
        <button id="audit-apply-btn" type="button">${escapeHtml(t("auditApply"))}</button>
      </div>`;
  }

  function renderPagination(data) {
    const hasPrev = data.page > 1;
    const hasNext = data.page < data.pages;
    if (!hasPrev && !hasNext) return "";
    return `
      <div class="audit-pagination">
        <button id="audit-prev-btn" type="button" ${hasPrev ? "" : "disabled"}>${escapeHtml(t("auditPrev"))}</button>
        <span>${data.page} / ${data.pages}</span>
        <button id="audit-next-btn" type="button" ${hasNext ? "" : "disabled"}>${escapeHtml(t("auditNext"))}</button>
      </div>`;
  }

  function renderTable(data) {
    if (!data.records || data.records.length === 0) {
      return `<div class="audit-empty"><span>—</span>${escapeHtml(t("auditEmpty"))}</div>`;
    }
    const rows = data.records.map(renderRecord).join("");
    return `
      <div class="audit-table-wrapper">
        <table class="audit-table">
          <thead>
            <tr>
              <th>${escapeHtml(t("auditActor"))}</th>
              <th>${escapeHtml(t("auditAction"))}</th>
              <th>${escapeHtml(t("auditTarget"))}</th>
              <th>${escapeHtml(t("auditResult"))}</th>
              <th>${escapeHtml(t("auditDate"))}</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      ${renderPagination(data)}`;
  }

  // ------------------------------------------------------------------
  // Event wiring
  // ------------------------------------------------------------------

  function bindControls() {
    const applyBtn = $("#audit-apply-btn");
    const prevBtn = $("#audit-prev-btn");
    const nextBtn = $("#audit-next-btn");

    if (applyBtn) {
      applyBtn.onclick = () => {
        actorFilter = ($("#audit-actor-input")?.value || "").trim();
        actionFilter = ($("#audit-action-input")?.value || "").trim();
        page = 1;
        renderAuditPanel();
      };
    }
    if (prevBtn) {
      prevBtn.onclick = () => { page -= 1; renderAuditPanel(); };
    }
    if (nextBtn) {
      nextBtn.onclick = () => { page += 1; renderAuditPanel(); };
    }
  }

  // ------------------------------------------------------------------
  // Main render
  // ------------------------------------------------------------------

  async function renderAuditPanel() {
    const generation = ++renderGeneration;
    const params = new URLSearchParams({ page: String(page), page_size: "25" });
    if (actorFilter) params.set("actor", actorFilter);
    if (actionFilter) params.set("action", actionFilter);

    let data;
    try {
      data = await api(`/api/audit?${params.toString()}`);
    } catch (err) {
      if (generation !== renderGeneration) return;
      toast(err.message, true);
      return;
    }
    if (generation !== renderGeneration) return;

    content.innerHTML = `
      <section class="audit-panel">
        <div class="block-panel hero">
          <div class="grass-edge"></div>
          <div class="audit-hero">
            <div>
              <span class="eyebrow">CRAFTCONTROL</span>
              <h2>${escapeHtml(t("auditTitle"))}</h2>
            </div>
          </div>
        </div>
        <div class="block-panel" style="padding:0;overflow:hidden;">
          ${renderFilters()}
          ${renderTable(data)}
        </div>
      </section>`;

    bindControls();
  }

  return { renderAuditPanel };
}
