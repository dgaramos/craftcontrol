function el(tag, className = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function text(parent, tag, content, className = "") {
  const node = el(tag, className);
  node.textContent = String(content ?? "");
  parent.append(node);
  return node;
}

function icon(parent, svg) {
  const range = document.createRange();
  parent.append(range.createContextualFragment(svg));
}

function statCard(label, value, note = "") {
  const article = el("article", "health-stat");
  text(article, "small", label);
  text(article, "b", value);
  if (note) text(article, "span", note, "health-stat-note");
  return article;
}

function healthBadge(status, t) {
  const badge = el("span", `health-badge health-${status}`);
  badge.textContent = t(status) || status;
  return badge;
}

function capabilityRow(key, cap) {
  const row = el("li", "capability-row");
  const supported = typeof cap === "object" && cap !== null && cap.supported === true;
  row.classList.add(supported ? "cap-supported" : "cap-unsupported");
  const name = el("span", "cap-name");
  name.textContent = key;
  const mark = el("span", "cap-mark");
  mark.textContent = supported ? "✓" : "✗";
  row.append(mark, name);
  return row;
}

export function createHealthPanel({ content, t, uiIcon, api, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, formatDate }) {
  return async function renderHealthPanel() {
    const screen = el("div", "health-screen");

    const switchWrapper = el("div");
    const range = document.createRange();
    switchWrapper.append(range.createContextualFragment(analyticsViewSwitch("health")));
    screen.append(switchWrapper);

    const hero = el("header", "health-hero block-panel");
    const heroCopy = el("div");
    text(heroCopy, "span", "BEHAVIOR PACK", "eyebrow");
    text(heroCopy, "h2", t("packHealthTitle"));
    text(heroCopy, "p", t("packHealthHelp"));
    const refreshBtn = el("button", "secondary");
    refreshBtn.id = "health-refresh";
    refreshBtn.type = "button";
    icon(refreshBtn, uiIcon("refresh"));
    refreshBtn.append(document.createTextNode(` ${t("refreshData")}`));
    hero.append(heroCopy, refreshBtn);
    screen.append(hero);

    const target = el("div");
    target.id = "health-content";
    screen.append(target);

    content.replaceChildren(screen);
    bindAnalyticsViewSwitch();

    const load = async () => {
      target.replaceChildren(
        Object.assign(el("div", "analytics-loading"), { textContent: t("checking") }),
      );
      try {
        const [pack, activity] = await Promise.all([
          api("/api/telemetry-pack"),
          api("/api/analytics/activity?kind=all&days=0&page=1&page_size=1"),
        ]);

        const health = pack.health || "waiting";
        const totalEvents = typeof activity.total === "number" ? activity.total : "—";
        const sequence = pack.sequence != null ? String(pack.sequence) : "—";
        const gapCount = pack.gap_count != null ? pack.gap_count : 0;
        const missingEvents = pack.missing_events != null ? pack.missing_events : 0;
        const resetCount = pack.reset_count != null ? pack.reset_count : 0;

        if (health === "waiting" && pack.installed === false) {
          const empty = el("div", "analytics-empty");
          text(empty, "p", t("noPackHealth"));
          target.replaceChildren(empty);
          return;
        }

        const fragment = document.createDocumentFragment();

        const statusSection = el("section", "health-status block-panel");
        const statusTitle = el("div", "ranking-section-title");
        text(statusTitle, "span", "STATUS", "eyebrow");
        text(statusTitle, "h3", t("packHealth"));
        statusSection.append(statusTitle);
        const statusRow = el("div", "health-status-row");
        statusRow.append(healthBadge(health, t));
        if (pack.runtime_version) {
          const ver = el("span", "health-version");
          ver.textContent = `v${escapeHtml(pack.runtime_version)}`;
          statusRow.append(ver);
        }
        if (pack.last_error) {
          const err = el("p", "health-error");
          err.textContent = pack.last_error;
          statusSection.append(statusRow, err);
        } else {
          statusSection.append(statusRow);
        }
        const freshness = el("p", "health-freshness");
        text(freshness, "span", t("lastResponse") + " " + formatDate(pack.last_response_at));
        text(freshness, "small", t("updated") + " " + formatDate(pack.last_snapshot_at));
        statusSection.append(freshness);
        fragment.append(statusSection);

        const volumeSection = el("section", "health-volume block-panel");
        const volTitle = el("div", "ranking-section-title");
        text(volTitle, "span", "VOLUME", "eyebrow");
        text(volTitle, "h3", t("eventVolume"));
        volumeSection.append(volTitle);
        const volGrid = el("div", "health-stats-grid");
        volGrid.append(
          statCard(t("eventCount", totalEvents), totalEvents, t("lifetime")),
          statCard(t("telemetrySequence"), sequence),
          statCard(t("detectedGaps"), gapCount),
          statCard(t("missingEvents"), missingEvents),
          statCard(t("resetCount"), resetCount),
          statCard(t("lastGap"), pack.last_gap || "—"),
        );
        volumeSection.append(volGrid);
        fragment.append(volumeSection);

        const seqSection = el("section", "health-sequence block-panel");
        const seqTitle = el("div", "ranking-section-title");
        text(seqTitle, "span", "TELEMETRY", "eyebrow");
        text(seqTitle, "h3", t("sequenceHealth"));
        seqSection.append(seqTitle);
        const seqGrid = el("div", "health-stats-grid");
        seqGrid.append(
          statCard(t("lastSnapshot"), formatDate(pack.last_snapshot_at)),
          statCard(t("lastResponse"), formatDate(pack.last_response_at)),
          statCard(t("installedVersion"), pack.installed_version || "—"),
          statCard(t("bundledVersion"), pack.source_version || "—"),
          statCard(t("storageVersion"), pack.storage_version || "—"),
          statCard(t("storageStatus"), pack.storage_status || "—"),
        );
        seqSection.append(seqGrid);
        fragment.append(seqSection);

        const capabilities = pack.capabilities && typeof pack.capabilities === "object"
          ? pack.capabilities
          : {};
        const capKeys = Object.keys(capabilities);
        if (capKeys.length) {
          const capSection = el("section", "health-capabilities block-panel");
          const capTitle = el("div", "ranking-section-title");
          const capStatus = pack.capability_status === "full" ? t("capabilityFull") : t("capabilityLimited");
          text(capTitle, "span", capStatus, "eyebrow");
          text(capTitle, "h3", t("capabilities"));
          capSection.append(capTitle);
          const capList = el("ul", "capability-list");
          capKeys.forEach((key) => capList.append(capabilityRow(key, capabilities[key])));
          capSection.append(capList);
          fragment.append(capSection);
        }

        target.replaceChildren(fragment);
      } catch (error) {
        const empty = el("div", "analytics-empty");
        text(empty, "p", escapeHtml(error.message));
        target.replaceChildren(empty);
      }
    };

    refreshBtn.onclick = load;
    await load();
  };
}
