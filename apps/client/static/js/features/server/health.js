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


function statCard(label, value, note = "") {
  const article = el("article", "health-stat");
  text(article, "small", label);
  text(article, "b", value);
  if (note) text(article, "span", note, "health-stat-note");
  return article;
}


function capabilityRow(key, cap, uiIcon) {
  const row = el("li", "capability-row");
  const supported = typeof cap === "object" && cap !== null && cap.supported === true;
  row.classList.add(supported ? "cap-supported" : "cap-unsupported");
  const name = el("span", "cap-name");
  name.textContent = key;
  const mark = el("span", "cap-mark");
  mark.innerHTML = uiIcon(supported ? "check" : "close");
  row.append(mark, name);
  return row;
}

/**
 * The pack's technical detail, folded away inside the Telemetry Pack screen.
 *
 * Sequence, gaps, storage and capabilities: the numbers that only matter while
 * something is wrong. Health, versions and freshness are *not* here — the
 * screen states those once, at the top, where the question is asked.
 */
export function createPackHealthPanel({ $, t, api, formatDate, uiIcon }) {
  return async function renderPackHealth() {
    const content = $("#pack-health");
    if (!content) return;
    const screen = el("div", "health-screen");
    const target = el("div");
    target.id = "health-content";
    screen.append(target);

    content.replaceChildren(screen);

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

        const volumeSection = el("section", "health-volume block-panel");
        const volTitle = el("div", "ranking-section-title");
        text(volTitle, "span", t("volumeEyebrow"), "eyebrow");
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
        text(seqTitle, "span", t("telemetryEyebrow"), "eyebrow");
        text(seqTitle, "h3", t("sequenceHealth"));
        seqSection.append(seqTitle);
        const seqGrid = el("div", "health-stats-grid");
        seqGrid.append(
          statCard(t("lastSnapshot"), formatDate(pack.last_snapshot_at)),
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
          capKeys.forEach((key) => capList.append(capabilityRow(key, capabilities[key], uiIcon)));
          capSection.append(capList);
          fragment.append(capSection);
        }

        target.replaceChildren(fragment);
      } catch (error) {
        const empty = el("div", "analytics-empty");
        text(empty, "p", error.message);
        target.replaceChildren(empty);
      }
    };

    await load();
  };
}
