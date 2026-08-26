const periodDefinitions = {
  play_seconds: { label: "playTime", format: "duration" },
  sessions: { label: "explorationSessions", format: "number" },
  blocks_broken: { label: "rankBlocksBroken", format: "number" },
  blocks_placed: { label: "rankBlocksPlaced", format: "number" },
  mob_kills: { label: "combatMobKills", format: "number" },
  player_kills: { label: "combatPlayerKills", format: "number" },
  deaths: { label: "combatDeaths", format: "number" },
  distance: { label: "distanceTraveled", format: "distance" },
};

function calendarDate(day, localeTag) {
  const date = new Date(`${typeof day === "string" ? day : ""}T12:00:00`);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString(localeTag(), { day: "2-digit", month: "short" });
}

function validHour(value) {
  const hour = Number(value);
  return Number.isInteger(hour) && hour >= 0 && hour <= 23 ? hour : null;
}

function sessionCount(value) {
  const sessions = Number(value);
  return Number.isFinite(sessions) && sessions >= 0 ? sessions : 0;
}

function metricValue(value) {
  const metric = Number(value);
  return Number.isFinite(metric) && metric >= 0 ? metric : 0;
}

function levelFor(value, maximum) {
  return Math.max(0, Math.min(4, Math.ceil((metricValue(value) / maximum) * 4)));
}

function element(tag, className = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  return node;
}

function appendText(parent, tag, text, className = "") {
  const node = element(tag, className);
  node.textContent = String(text ?? "");
  parent.append(node);
  return node;
}

function appendIcon(parent, icon) {
  const range = document.createRange();
  parent.append(range.createContextualFragment(icon));
}

function button(text, dataset = {}, className = "") {
  const node = element("button", className);
  node.type = "button";
  Object.assign(node.dataset, dataset);
  node.textContent = text;
  return node;
}

function heading(label, title) {
  const container = element("div", "ranking-section-title");
  appendText(container, "span", label, "eyebrow");
  appendText(container, "h3", title);
  return container;
}

function renderCalendar(calendar, days, maxDay, formatDuration, sessionsLabel, dateLabel) {
  days.forEach((day) => {
    const article = element("article", `level-${levelFor(day?.play_seconds, maxDay)}`);
    const date = dateLabel(day?.day);
    article.title = date;
    appendText(article, "span", date);
    appendText(article, "b", metricValue(day?.play_seconds) ? formatDuration(metricValue(day.play_seconds)) : "—");
    appendText(article, "small", `${sessionCount(day?.sessions)} ${sessionsLabel.toLocaleLowerCase()}`);
    calendar.append(article);
  });
}

function renderHeatmap(grid, heatmap, weekdays, maxHeat, formatDuration) {
  appendText(grid, "span", "");
  Array.from({ length: 24 }, (_, hour) => appendText(grid, "b", String(hour).padStart(2, "0")));
  weekdays.forEach((weekday, weekdayIndex) => {
    appendText(grid, "strong", weekday);
    heatmap.filter((cell) => cell?.weekday === weekdayIndex).forEach((cell) => {
      const hour = validHour(cell?.hour);
      if (hour === null) return;
      const item = element("i", `level-${levelFor(cell.seconds, maxHeat)}`);
      item.title = `${weekday} ${String(hour).padStart(2, "0")}:00 · ${formatDuration(metricValue(cell.seconds))}`;
      grid.append(item);
    });
  });
}

export function createTrendsPanel({ state, content, t, uiIcon, api, $, analyticsViewSwitch, bindAnalyticsViewSwitch, formatRankingValue, openAnalyticsPlayer, formatDate, formatDuration, localeTag }) {
  return async function renderTrendsPanel() {
    const analytics = state.analytics;
    const screen = element("div", "trends-screen");
    const viewSwitch = element("div");
    appendIcon(viewSwitch, analyticsViewSwitch("trends"));
    screen.append(viewSwitch);

    const hero = element("header", "trends-hero block-panel");
    const heroCopy = element("div");
    appendText(heroCopy, "span", t("dailyHistory"), "eyebrow");
    appendText(heroCopy, "h2", t("trendsTitle"));
    appendText(heroCopy, "p", t("trendsHelp"));
    const refresh = button(t("refreshData"), {}, "secondary");
    refresh.id = "trends-refresh";
    appendIcon(refresh, uiIcon("refresh"));
    hero.append(heroCopy, refresh);
    screen.append(hero);

    const periodSwitch = element("div", "period-switch");
    [7, 30].forEach((days) => periodSwitch.append(button(t(days === 7 ? "sevenDays" : "thirtyDays"), { periodDays: String(days) }, analytics.periodDays === days ? "active" : "")));
    screen.append(periodSwitch);

    const target = element("div");
    target.id = "trends-content";
    screen.append(target);
    content.replaceChildren(screen);
    bindAnalyticsViewSwitch();

    const load = async () => {
      const loadingDiv = element("div", "analytics-loading");
      appendText(loadingDiv, "span", t("checking"));
      target.replaceChildren(loadingDiv);
      try {
        const result = await api(`/api/analytics/periods?days=${analytics.periodDays}&limit=10`);
        const definition = periodDefinitions[analytics.periodMetric] || periodDefinitions.play_seconds;
        const ranking = Array.isArray(result?.rankings?.[analytics.periodMetric]) ? result.rankings[analytics.periodMetric] : [];
        const days = Array.isArray(result?.calendar) ? result.calendar : [];
        const heatmap = Array.isArray(result?.heatmap) ? result.heatmap.filter((cell) => validHour(cell?.hour) !== null) : [];
        const maxDay = Math.max(1, ...days.map((day) => metricValue(day?.play_seconds)));
        const maxHeat = Math.max(1, ...heatmap.map((cell) => metricValue(cell?.seconds)));
        const totals = result?.totals && typeof result.totals === "object" ? result.totals : {};
        const dateLabel = (day) => calendarDate(day, localeTag);

        const fragment = document.createDocumentFragment();
        const note = element("p", "trends-note");
        appendText(note, "span", t("collectionStarted"));
        appendText(note, "small", `${result?.timezone || ""} · ${t("updated")} ${formatDate(result?.generated_at)}`);
        fragment.append(note);

        const summary = element("section", "trends-summary");
        [["playTime", formatDuration(metricValue(totals.play_seconds))], ["explorationSessions", formatRankingValue(metricValue(totals.sessions), "number")], ["dailyBlocks", formatRankingValue(metricValue(totals.blocks_broken) + metricValue(totals.blocks_placed), "number")], ["dailyKills", formatRankingValue(metricValue(totals.mob_kills) + metricValue(totals.player_kills), "number")], ["mostActiveDay", result?.most_active_day?.day ? dateLabel(result.most_active_day.day) : "—"]].forEach(([label, value]) => {
          const item = element("article");
          appendText(item, "small", t(label));
          appendText(item, "b", value);
          summary.append(item);
        });
        fragment.append(summary);

        const metricPicker = element("div", "period-metric-picker");
        Object.entries(periodDefinitions).forEach(([key, item]) => {
          const metricButton = button(t(item.label), { periodMetric: key }, analytics.periodMetric === key ? "active" : "");
          metricButton.onclick = () => { analytics.periodMetric = metricButton.dataset.periodMetric; load(); };
          metricPicker.append(metricButton);
        });
        fragment.append(metricPicker);

        const main = element("div", "trends-main-grid");
        const rankingPanel = element("section", "period-ranking block-panel");
        rankingPanel.append(heading(t("periodDaysLabel", analytics.periodDays), `${t("periodRanking")}: ${t(definition.label)}`));
        if (ranking.length) {
          const list = element("ol");
          ranking.forEach((entry, index) => {
            const row = element("li");
            appendText(row, "b", index + 1);
            const player = button(entry?.player?.name || "", { periodPlayer: entry?.player?.id || "" });
            player.onclick = () => openAnalyticsPlayer(player.dataset.periodPlayer);
            row.append(player);
            appendText(row, "strong", formatRankingValue(metricValue(entry?.value), definition.format));
            list.append(row);
          });
          rankingPanel.append(list);
        } else {
          const zero = element("div", "trends-zero");
          const icon = element("span");
          appendIcon(icon, uiIcon("periods"));
          zero.append(icon);
          appendText(zero, "p", t("noPeriodData"));
          rankingPanel.append(zero);
        }
        const calendarPanel = element("section", "activity-calendar block-panel");
        calendarPanel.append(heading(t("periodDaysLabel", analytics.periodDays), t("activityCalendar")));
        const calendar = element("div", "calendar-grid");
        calendar.dataset.trendsCalendar = "";
        renderCalendar(calendar, days, maxDay, formatDuration, t("explorationSessions"), dateLabel);
        calendarPanel.append(calendar);
        main.append(rankingPanel, calendarPanel);
        fragment.append(main);

        const heatmapPanel = element("section", "heatmap-panel block-panel");
        heatmapPanel.append(heading(result?.timezone || "", t("sessionHeatmap")));
        const scroll = element("div", "heatmap-scroll");
        const grid = element("div", "heatmap-grid");
        grid.dataset.trendsHeatmap = "";
        renderHeatmap(grid, heatmap, Array.isArray(t("weekdayShort")) ? t("weekdayShort") : [], maxHeat, formatDuration);
        scroll.append(grid);
        heatmapPanel.append(scroll);
        const legend = element("div", "heatmap-legend");
        appendText(legend, "span", t("lessActive"));
        Array.from({ length: 5 }, (_, level) => legend.append(element("i", `level-${level}`)));
        appendText(legend, "span", t("moreActive"));
        heatmapPanel.append(legend);
        fragment.append(heatmapPanel);
        target.replaceChildren(fragment);
      } catch (error) {
        const empty = element("div", "analytics-empty");
        appendText(empty, "p", error?.message || "");
        target.replaceChildren(empty);
      }
    };

    periodSwitch.querySelectorAll("[data-period-days]").forEach((periodButton) => {
      periodButton.onclick = () => {
        analytics.periodDays = Number(periodButton.dataset.periodDays);
        periodSwitch.querySelectorAll("[data-period-days]").forEach((item) => item.classList.toggle("active", item === periodButton));
        load();
      };
    });
    refresh.onclick = load;
    await load();
  };
}
