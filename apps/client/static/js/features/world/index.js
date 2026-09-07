import { persistTab } from "../../core/route.js?v=7";

export function createWorldFeature({ state, content, t, api, $, uiIcon, toast, getSettingsFeature, getNavigation }) {
function renderTimePanel() {
  const presets = ["sunrise", "day", "noon", "sunset", "night", "midnight"];
  const presetIcons = { sunrise: "sun", day: "sun", noon: "sun", sunset: "sun", night: "moon", midnight: "moon" };
  const settings = getSettingsFeature();
  content.innerHTML = `
    <div class="time-screen">
      <button type="button" class="time-back btn" data-time-back>
        ${uiIcon("chevron")}<span>${t("navHome")}</span>
      </button>
      <section class="time-world block-panel">
        <div class="grass-edge" aria-hidden="true"></div>
        <div class="world-summary">
          <div><small>${t("homeDay")}</small><strong id="time-world-day">—</strong></div>
          <div><span class="world-label-row"><small>${t("homeTime")}</small><small id="time-world-ticks" class="world-ticks"></small></span><span class="world-value">${uiIcon("sun", "", "js-time-world-icon")}<strong id="time-world-time">—</strong></span></div>
          <div class="world-weather" id="time-world-weather-cell"><small>${t("homeWeather")}</small><span class="world-value">${uiIcon("sun", "", "js-time-weather-icon")}<strong id="time-world-weather">—</strong></span></div>
        </div>
      </section>
      <section class="time-group">
        <span class="eyebrow">${t("timeOfDay")}</span>
        <div class="time-presets">${presets.map((preset) => `<button type="button" data-time-preset="${preset}"><span>${uiIcon(presetIcons[preset])}</span>${t(preset)}</button>`).join("")}</div>
      </section>
      <section class="time-group">
        <span class="eyebrow">${t("weatherTitle")}</span>
        <div class="weather-options">
          <button data-weather="clear" class="weather-clear">${uiIcon("sun")} ${t("clear")}</button>
          <button data-weather="rain" class="weather-rain">${uiIcon("rain")} ${t("rain")}</button>
          <button data-weather="thunder" class="weather-thunder">${uiIcon("thunder")} ${t("thunder")}</button>
        </div>
        <div class="weather-duration-row">
          <span>${t("duration")}</span>
          <input id="weather-duration" type="number" min="1" max="1000000" placeholder="${t("duration")}">
        </div>
      </section>
      <section class="time-group">
        <span class="eyebrow time-group-label">${t("cycles")}<b>${t("instant")}</b></span>
        <div class="block-panel time-cycles">
          <div class="cycle-row"><div><strong>${t("daylightCycle")}</strong><small>${state.locale === "pt" ? "Desative para congelar o horário atual." : "Disable to freeze the current time."}</small></div>${settings.booleanControl("time-daylight-cycle", state.gamerules.dodaylightcycle)}</div>
          <div class="cycle-row"><div><strong>${t("weatherCycle")}</strong><small>${state.locale === "pt" ? "Desative para manter o clima escolhido." : "Disable to keep the selected weather."}</small></div>${settings.booleanControl("time-weather-cycle", state.gamerules.doweathercycle)}</div>
        </div>
      </section>
      <details class="time-advanced">
        <summary><span>${t("advancedControls")}</span>${uiIcon("chevron")}</summary>
        <div class="time-advanced-body">
          <div><span class="eyebrow">${t("exactTime")}</span><div class="command-row"><input id="exact-time" type="number" min="0" max="24000" value="0"><button type="button" id="set-exact-time" class="primary">${t("setTime")}</button></div></div>
          <div><span class="eyebrow">${t("advanceTime")}</span><div class="command-row"><input id="add-time" type="number" min="1" max="240000" value="1000"><button type="button" id="add-time-button">${t("addTime")}</button></div></div>
          <div>
            <span class="eyebrow">${t("timeQueries")}</span>
            <div class="query-buttons">
              <button data-time-query="daytime">${t("daytime")}</button>
              <button data-time-query="gametime">${t("gametime")}</button>
              <button data-time-query="day">${t("days")}</button>
              <button id="weather-query">${t("queryWeather")}</button>
            </div>
            <output id="time-query-result">${t("queryResult")}: —</output>
          </div>
        </div>
      </details>
      <section class="time-danger">
        <div><strong>${t("resetDays")}</strong><small>${t("resetDaysHelp")}</small></div>
        <button id="reset-days" class="danger">${t("resetDays")}</button>
      </section>
    </div>`;
  bindTimePanel();
  mirrorWorldSummary();
}

/* The Home hero owns the live clock; this screen mirrors its current values so
   the reading and the controls sit together. */
function mirrorWorldSummary() {
  const pairs = [["#world-day", "#time-world-day"], ["#world-ticks", "#time-world-ticks"], ["#world-time", "#time-world-time"], ["#world-weather", "#time-world-weather"]];
  pairs.forEach(([from, to]) => {
    const source = $(from);
    const target = $(to);
    if (source && target) target.textContent = source.textContent;
  });
  if (typeof document === "undefined") return;
  const weatherCell = document.querySelector(".world-weather[data-weather]");
  const mirrorCell = $("#time-world-weather-cell");
  if (weatherCell && mirrorCell) mirrorCell.dataset.weather = weatherCell.dataset.weather;
  [["#world-time-icon", ".js-time-world-icon use"], ["#world-weather-icon", ".js-time-weather-icon use"]].forEach(([from, to]) => {
    const source = $(from);
    const target = document.querySelector(to);
    const href = source?.getAttribute("href");
    if (target && href && target.getAttribute("href") !== href) target.setAttribute("href", href);
  });
}

const READ_ONLY_TIME_ACTIONS = new Set(["weather-query", "query"]);

async function runTimeAction(action, payload = {}) {
  const result = await api(`/api/time/${action}`, { method: "POST", body: JSON.stringify(payload) });
  if (!READ_ONLY_TIME_ACTIONS.has(action)) toast(t("timeUpdated"));
  return result;
}

function bindTimePanel() {
  const guardMutation = (fn) => async (...args) => {
    if (state.operationActive) { toast(t("operationLocked"), true); return; }
    return fn(...args);
  };
  content.querySelectorAll("[data-time-back]").forEach((button) => button.onclick = () => { state.tab = "home"; });
  content.querySelectorAll("[data-time-preset]").forEach((button) => button.onclick = guardMutation(async () => {
    try { await runTimeAction("preset", { value: button.dataset.timePreset }); } catch (error) { toast(error.message, true); }
  }));
  $("#set-exact-time").onclick = guardMutation(async () => {
    try { await runTimeAction("set", { value: $("#exact-time").value }); } catch (error) { toast(error.message, true); }
  });
  $("#add-time-button").onclick = guardMutation(async () => {
    try { await runTimeAction("add", { value: $("#add-time").value }); } catch (error) { toast(error.message, true); }
  });
  [["time-daylight-cycle", "dodaylightcycle"], ["time-weather-cycle", "doweathercycle"]].forEach(([id, rule]) => {
    $(`#${id}`).onchange = async (event) => {
      if (state.operationActive) { toast(t("operationLocked"), true); renderTimePanel(); return; }
      getSettingsFeature().updateToggleLabel(event.target);
      try {
        await api(`/api/gamerules/${rule}`, { method: "PUT", body: JSON.stringify({ value: event.target.checked }) });
        state.gamerules[rule] = String(event.target.checked);
      } catch (error) { toast(error.message, true); renderTimePanel(); }
    };
  });
  content.querySelectorAll("[data-weather]").forEach((button) => button.onclick = guardMutation(async () => {
    try { await runTimeAction("weather", { value: button.dataset.weather, duration: $("#weather-duration").value }); } catch (error) { toast(error.message, true); }
  }));
  $("#weather-query").onclick = async () => {
    try { const result = await runTimeAction("weather-query"); $("#time-query-result").textContent = `${t("queryResult")}: ${t(result.value) || result.value}`; } catch (error) { toast(error.message, true); }
  };
  content.querySelectorAll("[data-time-query]").forEach((button) => button.onclick = async () => {
    try {
      const result = await runTimeAction("query", { value: button.dataset.timeQuery });
      $("#time-query-result").textContent = `${t("queryResult")}: ${result.value ?? t("queryUnavailable")}`;
    } catch (error) { toast(error.message, true); }
  });
  $("#reset-days").onclick = guardMutation(async () => {
    if (!confirm(t("resetDaysConfirm"))) return;
    try { await runTimeAction("reset-days"); } catch (error) { toast(error.message, true); }
  });
}


  const openTimeControls = () => {
    state.tab = "__time__";
    persistTab(state.tab);
    getNavigation().renderTabs();
    renderTimePanel();
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const renderWorld = () => {
    const prefix = `<button class="section-feature" id="open-time"><span>${uiIcon("sun")}</span><div><strong>${t("timeControls")}</strong><small>${t("timeControlsHint")}</small></div><b>›</b></button>`;
    getSettingsFeature().renderSettingsGroups(["Geral", "Mundo"], prefix);
    $("#open-time").onclick = openTimeControls;
  };
  return { renderWorld, renderTimePanel, openTimeControls };
}
