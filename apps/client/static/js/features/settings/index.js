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
      return `<span class="read-only-badge">${t("readOnlyLabel")}</span>`;
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
    // The changes bar announces the count and opens the drawer; this keeps the
    // profile dot and a drawer already on screen in step with the state.
    const count = Object.keys(state.changes).length;
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
    // Handoff layout: the before → after pair reads first, with the technical
    // key as a quiet caption underneath.
    $("#changes-list").innerHTML = entries.map(([key, value]) => {
      const definition = definitionFor(key);
      return `<article class="change-item"><div class="change-values"><span><small>${t("currentValue")}</small><b class="change-before">${escapeHtml(displayValue(state.config[key], definition))}</b></span><i aria-hidden="true">→</i><span><small>${t("newValue")}</small><b class="change-after">${escapeHtml(displayValue(value, definition))}</b></span></div><button type="button" class="remove-change" data-remove-change="${escapeHtml(key)}" aria-label="${t("removeChange")}">${uiIcon("close")}</button><p class="change-key">${escapeHtml(key)} · ${escapeHtml(fieldLabel(definition))}</p></article>`;
    }).join("");
    $("#changes-list").querySelectorAll("[data-remove-change]").forEach((button) => button.onclick = () => {
      const remaining = { ...state.changes };
      delete remaining[button.dataset.removeChange];
      state.changes = remaining;
      refreshActivePanel();
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
    return `<section class="player-server-settings settings-screen"><header class="inner-heading"><span class="eyebrow">${t("generalPlayerRules")}</span><h3>${t("playerSettingsTitle")}</h3><p>${t("playerSettingsHelp")}</p></header><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, Object.hasOwn(state.changes, key) ? state.changes[key] : state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></section>`;
  }

  function renderSettingsGroups(groupNames, prefix = "") {
    const titleKey = state.tab === "world" ? "worldIntro" : state.tab === "rules" ? "rulesIntro" : "serverIntro";
    const kickerKey = state.tab === "world" ? "configuration" : state.tab === "rules" ? "instant" : "infrastructure";
    const lockBanner = state.operationActive
      ? `<div class="mutation-lock-notice" role="alert">${t("operationLocked")}</div>`
      : "";
    content.innerHTML = `<section class="settings-screen"><header class="inner-heading"><span class="eyebrow">${t(kickerKey)}</span><h2>${t(titleKey)}</h2></header>${prefix}${lockBanner}<div class="accordion-list">${settingsMarkup(groupNames)}</div></section>`;
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
        const next = { ...state.changes };
        if (comparableValue(value) === comparableValue(state.config[key])) delete next[key];
        else next[key] = value;
        state.changes = next;
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
