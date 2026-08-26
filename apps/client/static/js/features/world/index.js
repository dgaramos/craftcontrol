import { persistTab } from "../../core/route.js?v=7";

export function createWorldFeature({ state, content, t, api, $, uiIcon, toast, getSettingsFeature, getNavigation }) {
function renderTimePanel() {
  const presets = ["sunrise", "day", "noon", "sunset", "night", "midnight"];
  const presetIcons = { sunrise: "sun", day: "sun", noon: "sun", sunset: "sun", night: "moon", midnight: "moon" };
  content.innerHTML = `
    <div class="time-screen">
      <section class="time-card block-panel"><h3>${t("timeOfDay")}</h3><p>${state.locale === "pt" ? "Escolha um momento predefinido do ciclo completo." : "Choose a preset from the complete daylight cycle."}</p><div class="time-presets">${presets.map((preset) => `<button type="button" data-time-preset="${preset}"><span>${uiIcon(presetIcons[preset])}</span>${t(preset)}</button>`).join("")}</div></section>
      <section class="time-card block-panel"><h3>${t("exactTime")}</h3><p>${t("exactTimeHelp")}</p><div class="command-row"><input id="exact-time" type="number" min="0" max="24000" value="0"><button type="button" id="set-exact-time">${t("setTime")}</button></div><h3 class="subheading">${t("advanceTime")}</h3><p>${t("advanceTimeHelp")}</p><div class="command-row"><input id="add-time" type="number" min="1" max="240000" value="1000"><button type="button" id="add-time-button">${t("addTime")}</button></div></section>
      <section class="time-card block-panel"><h3>${t("cycles")}</h3><div class="cycle-row"><div><strong>${t("daylightCycle")}</strong><small>${state.locale === "pt" ? "Desative para congelar o horário atual." : "Disable to freeze the current time."}</small></div>${getSettingsFeature().booleanControl("time-daylight-cycle", state.gamerules.dodaylightcycle)}</div><div class="cycle-row"><div><strong>${t("weatherCycle")}</strong><small>${state.locale === "pt" ? "Desative para manter o clima escolhido." : "Disable to keep the selected weather."}</small></div>${getSettingsFeature().booleanControl("time-weather-cycle", state.gamerules.doweathercycle)}</div></section>
      <section class="time-card block-panel"><h3>${t("weatherTitle")}</h3><p>${state.locale === "pt" ? "Escolha o clima e, se quiser, uma duração em ticks." : "Choose the weather and optionally set a duration in ticks."}</p><div class="weather-options"><button data-weather="clear">${uiIcon("sun")} ${t("clear")}</button><button data-weather="rain">${uiIcon("rain")} ${t("rain")}</button><button data-weather="thunder">${uiIcon("thunder")} ${t("thunder")}</button></div><input id="weather-duration" type="number" min="1" max="1000000" placeholder="${t("duration")}"><button id="weather-query" class="secondary wide">${t("queryWeather")}</button></section>
      <section class="time-card block-panel"><h3>${t("timeQueries")}</h3><div class="query-buttons"><button data-time-query="daytime">${t("daytime")}</button><button data-time-query="gametime">${t("gametime")}</button><button data-time-query="day">${t("days")}</button></div><output id="time-query-result">${t("queryResult")}: —</output></section>
      <section class="time-card danger-zone block-panel"><h3>${t("resetDays")}</h3><p>${t("resetDaysHelp")}</p><button id="reset-days" class="danger wide">${t("resetDays")}</button></section>
    </div>`;
  bindTimePanel();
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
