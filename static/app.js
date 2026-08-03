const state = { schema: null, config: {}, gamerules: {}, players: [], online: 0, maxPlayers: 0, changes: {}, tab: "Geral" };
const $ = (selector) => document.querySelector(selector);
const content = $("#content");

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.style.background = error ? "#ffd2cf" : "#eef8ee";
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 2600);
}

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Falha na operação");
  return data;
}

function inputFor(key, definition, value, live = false) {
  const id = `field-${key}`;
  let input;
  if (live && definition.type === "boolean") {
    const current = value === "true" ? "Ativado" : value === "false" ? "Desativado" : "não consultado";
    input = `<select id="${id}"><option value="">Atual: ${current}</option><option value="true">Ativar</option><option value="false">Desativar</option></select>`;
  } else if (definition.type === "boolean") {
    input = `<label class="switch"><input id="${id}" type="checkbox" ${String(value) === "true" || value === true ? "checked" : ""}><span></span></label>`;
  } else if (definition.type === "select") {
    input = `<select id="${id}">${definition.options.map((option) => `<option ${option === value ? "selected" : ""}>${option}</option>`).join("")}</select>`;
  } else {
    input = `<input id="${id}" type="${definition.type}" value="${value ?? ""}" placeholder="${live && value == null ? "Não consultado" : ""}" ${definition.min !== undefined ? `min="${definition.min}"` : ""} ${definition.max !== undefined ? `max="${definition.max}"` : ""}>`;
  }
  return `<div class="field"><div><label for="${id}">${definition.label}</label><small>${definition.warning || (live ? "Aplicação imediata" : "Requer aplicar e reiniciar")}</small></div>${input}</div>`;
}

function render() {
  const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === state.tab);
  const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === state.tab);
  content.innerHTML = `<div class="group"><div class="group-title">${state.tab}</div><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></div>`;
  persistent.forEach(([key, definition]) => {
    const element = $(`#field-${key}`);
    element.addEventListener("change", () => {
      state.changes[key] = definition.type === "boolean" ? element.checked : element.value;
      $("#save").textContent = `Salvar (${Object.keys(state.changes).length})`;
    });
  });
  live.forEach(([key, definition]) => {
    const element = $(`#field-${key}`);
    element.addEventListener("change", async () => {
      if (element.value === "") return;
      try {
        await api(`/api/gamerules/${key}`, { method: "PUT", body: JSON.stringify({ value: element.value }) });
        state.gamerules[key] = element.value;
        toast(`${definition.label} atualizado`);
        render();
      } catch (error) { toast(error.message, true); }
    });
  });
}

function setStatus(status) {
  const element = $("#status");
  element.textContent = status.online ? "● Online" : "○ Parado";
  element.classList.toggle("online", status.online);
  $("#server-state-title").textContent = status.online ? "Servidor online" : "Servidor parado";
  $("#hero").classList.toggle("offline", !status.online);
}

async function loadState() {
  const snapshot = await api("/api/state");
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  showPlayers(snapshot);
  render();
}

function showPlayers(snapshot) {
  state.players = snapshot.players || [];
  state.online = snapshot.online || 0;
  state.maxPlayers = snapshot.max_players || 0;
  $("#players-summary").textContent = `${state.online} / ${state.maxPlayers || "?"} jogadores online`;
  $("#players-list").textContent = state.players.length ? state.players.join(" · ") : "Ninguém conectado";
  $("#updated-at").textContent = snapshot.updated_at ? `Atualizado ${new Date(snapshot.updated_at * 1000).toLocaleTimeString("pt-BR")}` : "Aguardando atualização";
}

async function boot() {
  const [schema, snapshot, status] = await Promise.all([api("/api/schema"), api("/api/state"), api("/api/status")]);
  state.schema = schema;
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  showPlayers(snapshot);
  const tabs = [...new Set([...Object.values(schema.settings), ...Object.values(schema.gamerules)].map((item) => item.group))];
  $("#tabs").innerHTML = tabs.map((tab) => `<button class="${tab === state.tab ? "active" : ""}">${tab}</button>`).join("");
  $("#tabs").querySelectorAll("button").forEach((button) => button.onclick = () => {
    state.tab = button.textContent;
    $("#tabs").querySelectorAll("button").forEach((item) => item.classList.toggle("active", item === button));
    render();
  });
  setStatus(status);
  render();
}

$("#refresh").onclick = async () => {
  try {
    $("#refresh").classList.add("spinning");
    await api("/api/refresh", { method: "POST" });
    toast("Consultando o servidor…");
    setTimeout(async () => { await loadState(); $("#refresh").classList.remove("spinning"); toast("Estado atualizado"); }, 1800);
  } catch (error) { $("#refresh").classList.remove("spinning"); toast(error.message, true); }
};

$("#save").onclick = async () => {
  if (!Object.keys(state.changes).length) return toast("Nenhuma alteração pendente");
  try {
    await api("/api/config", { method: "PUT", body: JSON.stringify(state.changes) });
    toast("Salvo. Aplicando no servidor…");
    await api("/api/server/apply", { method: "POST" });
    state.changes = {};
    $("#save").textContent = "Salvar alterações";
    toast("Servidor atualizado");
  } catch (error) { toast(error.message, true); }
};

document.querySelectorAll("[data-world]").forEach((button) => button.onclick = async () => {
  try { await api(`/api/world/${button.dataset.world}`, { method: "POST" }); toast("Mundo atualizado"); }
  catch (error) { toast(error.message, true); }
});
$("#server-menu").onclick = () => $("#server-dialog").showModal();
$("#close-dialog").onclick = () => $("#server-dialog").close();
document.querySelectorAll("[data-server]").forEach((button) => button.onclick = async () => {
  if (!confirm(`${button.textContent} o servidor?`)) return;
  try {
    await api(`/api/server/${button.dataset.server}`, { method: "POST" });
    toast("Operação concluída");
    $("#server-dialog").close();
    setTimeout(async () => setStatus(await api("/api/status")), 1500);
  } catch (error) { toast(error.message, true); }
});

boot().catch((error) => toast(error.message, true));
