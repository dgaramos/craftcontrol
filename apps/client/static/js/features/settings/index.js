export function createSettingsFeature({ state, content, t, api, $, escapeHtml, toast, uiIcon, optionLabel, localeTag, groupLabel, refreshActivePanel, document: documentRef = document }) {
  function can(capability) {
    const capabilities = state.user?.capabilities || [];
    return capabilities.includes("*") || capabilities.includes(capability);
  }

  function fieldLabel(definition) {
    return state.locale === "pt" ? definition.label : definition[`label_${state.locale}`] || definition.label_en;
  }

  function fieldDescription(definition) {
    return state.locale === "pt" ? definition.description : definition[`description_${state.locale}`] || definition.description_en;
  }

  function booleanControl(id, value) {
    const normalized = String(value).toLowerCase();
    const known = normalized === "true" || normalized === "false";
    const checked = normalized === "true";
    const text = known ? (checked ? t("enabled") : t("disabled")) : t("unknown");
    if (id === "detail-operator" && !can("players.manage_permissions")) {
      const readOnlyLabel = state.locale === "pt" ? "Somente leitura" : state.locale === "es" ? "Solo lectura" : "Read only";
      return `<span class="read-only-badge">${readOnlyLabel}</span>`;
    }
    return `<div class="toggle-control"><span class="toggle-value ${known ? "" : "unknown"}">${text}</span><label class="switch"><input id="${id}" type="checkbox" ${checked ? "checked" : ""}><span></span></label></div>`;
  }

  function segmentedControl(id, definition, value) {
    const options = definition.options.map((option) =>
      `<button type="button" class="segment ${option === value ? "active" : ""}" data-choice="${escapeHtml(option)}">${escapeHtml(optionLabel(option))}</button>`
    ).join("");
    return `<div class="segmented" role="radiogroup" aria-labelledby="label-${id}">${options}<input id="${id}" type="hidden" value="${escapeHtml(value)}"></div>`;
  }

  function inputFor(key, definition, value, live = false) {
    const id = `field-${key}`;
    let input;
    if (definition.type === "boolean") {
      input = booleanControl(id, value);
    } else if (definition.type === "select") {
      input = segmentedControl(id, definition, value);
    } else {
      input = `<input id="${id}" type="${definition.type}" value="${escapeHtml(value)}" placeholder="${live && value == null ? t("unknown") : ""}" ${definition.min !== undefined ? `min="${definition.min}"` : ""} ${definition.max !== undefined ? `max="${definition.max}"` : ""}>`;
    }
    const warningText = state.locale === "en" ? definition.warning_en : definition.warning;
    const warning = warningText ? `<small class="field-warning">${uiIcon("warning")} ${escapeHtml(warningText)}</small>` : "";
    return `<div class="field ${live ? "live-field" : ""}"><div class="field-copy"><label id="label-${id}" for="${id}">${escapeHtml(fieldLabel(definition))}</label><p>${escapeHtml(fieldDescription(definition))}</p>${warning}<small class="field-meta">${uiIcon(live ? "live" : "restart")} ${live ? t("immediate") : t("restartRequired")}</small></div>${input}</div>`;
  }

  function updateSaveLabel() {
    const count = Object.keys(state.changes).length;
    $("#save").hidden = count === 0 || state.operationActive;
    $("#save-label").textContent = t("reviewCount", count);
    documentRef.querySelector("footer").classList.toggle("has-pending", count > 0);
    const profileDot = documentRef.querySelector("#profile-dot");
    if (profileDot) profileDot.hidden = count === 0;
    if ($("#changes-drawer").open) renderChangesDrawer();
  }

  function comparableValue(value) {
    if (typeof value === "boolean") return String(value);
    return String(value ?? "").trim().toLowerCase();
  }

  function displayValue(value, definition) {
    if (definition.type === "boolean") return comparableValue(value) === "true" ? t("enabled") : t("disabled");
    if (definition.type === "select") return optionLabel(String(value));
    return String(value ?? "—");
  }

  function definitionFor(key) {
    return state.schema.settings[key];
  }

  function renderChangesDrawer() {
    const entries = Object.entries(state.changes);
    if (!entries.length) {
      $("#changes-drawer").close();
      return;
    }
    $("#changes-list").innerHTML = entries.map(([key, value]) => {
      const definition = definitionFor(key);
      return `<article class="change-item"><div class="change-copy"><strong>${escapeHtml(fieldLabel(definition))}</strong><div class="change-values"><span><small>${t("currentValue")}</small>${escapeHtml(displayValue(state.config[key], definition))}</span><b>→</b><span><small>${t("newValue")}</small>${escapeHtml(displayValue(value, definition))}</span></div></div><button type="button" class="remove-change" data-remove-change="${escapeHtml(key)}" aria-label="${t("removeChange")}">${uiIcon("close")}</button></article>`;
    }).join("");
    $("#changes-list").querySelectorAll("[data-remove-change]").forEach((button) => button.onclick = () => {
      delete state.changes[button.dataset.removeChange];
      refreshActivePanel();
      updateSaveLabel();
    });
  }

  function bindSegmentedControls() {
    content.querySelectorAll(".segmented").forEach((control) => {
      const input = control.querySelector("input");
      control.querySelectorAll(".segment").forEach((button) => {
        button.onclick = () => {
          control.querySelectorAll(".segment").forEach((item) => item.classList.toggle("active", item === button));
          input.value = button.dataset.choice;
          input.dispatchEvent(new Event("change"));
        };
      });
    });
  }

  function updateToggleLabel(element) {
    const label = element.closest(".toggle-control").querySelector(".toggle-value");
    label.textContent = element.checked ? t("enabled") : t("disabled");
    label.classList.remove("unknown");
  }

  function settingsMarkup(groupNames) {
    return groupNames.map((group, index) => {
      const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === group);
      const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === group);
      if (!persistent.length && !live.length) return "";
      const domain = persistent.length ? state.domains.settings : state.domains.gamerules;
      const observed = domain?.observed_at ? `${t("confirmedAt")} ${new Date(domain.observed_at * 1000).toLocaleTimeString(localeTag())}` : t("unknown");
      return `<details class="settings-accordion" ${index === 0 ? "open" : ""}><summary><span>${escapeHtml(groupLabel(group))}<small>${escapeHtml(observed)}</small></span><b>${persistent.length + live.length}</b></summary><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, Object.hasOwn(state.changes, key) ? state.changes[key] : state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></details>`;
    }).join("");
  }

  function playerSettingsMarkup() {
    const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === "Jogadores");
    const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === "Jogadores");
    return `<section class="player-server-settings block-panel"><div class="section-heading"><div><span class="eyebrow">${state.locale === "pt" ? "REGRAS GERAIS" : "GENERAL RULES"}</span><h3>${state.locale === "pt" ? "Configurações para todos os jogadores" : "Settings for every player"}</h3><p>${state.locale === "pt" ? "Limites e regras do servidor. Alterações instantâneas são identificadas pelo raio." : "Server-wide limits and rules. Instant changes are marked with a lightning bolt."}</p></div></div><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, Object.hasOwn(state.changes, key) ? state.changes[key] : state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></section>`;
  }

  function renderSettingsGroups(groupNames, prefix = "") {
    const titleKey = state.tab === "world" ? "worldIntro" : state.tab === "rules" ? "rulesIntro" : state.tab === "server" ? "serverIntro" : "onlinePlayers";
    const lockBanner = state.operationActive
      ? `<div class="mutation-lock-notice" role="alert">${t("operationLocked")}</div>`
      : "";
    content.innerHTML = `<div class="section-heading"><h2>${t(titleKey)}</h2></div>${prefix}${lockBanner}<div class="accordion-list">${settingsMarkup(groupNames)}</div>`;
    bindSegmentedControls();
    bindSettingFields(groupNames);
  }

  function bindSettingFields(groupNames) {
    const persistent = Object.entries(state.schema.settings).filter(([, definition]) => groupNames.includes(definition.group));
    const live = Object.entries(state.schema.gamerules).filter(([, definition]) => groupNames.includes(definition.group));
    if (state.operationActive) {
      [...persistent, ...live].forEach(([key]) => {
        const element = $(`#field-${key}`);
        if (element) element.disabled = true;
        const segmented = element?.closest(".segmented");
        if (segmented) segmented.querySelectorAll(".segment").forEach((btn) => { btn.disabled = true; });
      });
      return;
    }
    persistent.forEach(([key, definition]) => {
      const element = $(`#field-${key}`);
      element.addEventListener("change", () => {
        if (definition.type === "boolean") updateToggleLabel(element);
        const value = definition.type === "boolean" ? element.checked : element.value;
        if (comparableValue(value) === comparableValue(state.config[key])) delete state.changes[key];
        else state.changes[key] = value;
        updateSaveLabel();
      });
    });
    live.forEach(([key, definition]) => {
      const element = $(`#field-${key}`);
      element.addEventListener("change", async () => {
        const previous = state.gamerules[key];
        if (definition.type === "boolean") updateToggleLabel(element);
        const value = definition.type === "boolean" ? element.checked : element.value;
        try {
          await api(`/api/gamerules/${key}`, { method: "PUT", body: JSON.stringify({ value }) });
          state.gamerules[key] = String(value);
          toast(t("fieldUpdated", fieldLabel(definition)));
        } catch (error) {
          state.gamerules[key] = previous;
          toast(error.message, true);
          refreshActivePanel();
        }
      });
    });
  }

  return { booleanControl, bindSegmentedControls, bindSettingFields, playerSettingsMarkup, renderChangesDrawer, renderSettingsGroups, updateSaveLabel, updateToggleLabel };
}
