import { api } from "./api.js?v=7";

const locale = () => ["pt", "en", "es"].includes(localStorage.getItem("craftcontrol-locale")) ? localStorage.getItem("craftcontrol-locale") : "pt";
const copy = {
  pt: { title: "Entrar no CraftControl", claimTitle: "Criar acesso", player: "Gamertag", password: "Senha", login: "Entrar", noAccount: "Primeiro acesso ou recebeu um convite?", claim: "Criar acesso", token: "Código de convite", choose: "Escolha uma senha com pelo menos 8 caracteres", activate: "Cadastrar", back: "Já tem acesso? Entrar", logout: "Sair", showPassword: "Mostrar senha", hidePassword: "Ocultar senha" },
  en: { title: "Sign in to CraftControl", claimTitle: "Create access", player: "Gamertag", password: "Password", login: "Sign in", noAccount: "First access or received an invitation?", claim: "Sign up", token: "Invitation code", choose: "Choose a password with at least 8 characters", activate: "Sign up", back: "Already have access? Sign in", logout: "Sign out", showPassword: "Show password", hidePassword: "Hide password" },
  es: { title: "Entrar en CraftControl", claimTitle: "Crear acceso", player: "Gamertag", password: "Contraseña", login: "Entrar", noAccount: "¿Primer acceso o recibiste una invitación?", claim: "Registrarse", token: "Código de invitación", choose: "Elige una contraseña de al menos 8 caracteres", activate: "Registrarse", back: "¿Ya tienes acceso? Entrar", logout: "Salir", showPassword: "Mostrar contraseña", hidePassword: "Ocultar contraseña" },
};

function passwordInput(words, autocomplete, minimum = "") {
  return `<span class="password-control"><input name="password" type="password" ${minimum} autocomplete="${autocomplete}" required><button class="password-toggle" type="button" aria-label="${words.showPassword}" title="${words.showPassword}" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><use href="/static/craftcontrol-ui.svg?v=7#ui-eye"></use></svg></button></span>`;
}

export async function requireSession() {
  try {
    const result = await api("/api/auth/me");
    showIdentity(result.user);
    return result.user;
  } catch (error) {
    if (error.status !== 401) throw error;
    showAuth();
    return null;
  }
}

function showIdentity(user) {
  const container = document.querySelector("#identity");
  if (!container) return;
  container.hidden = false;
  const logoutLabel = copy[locale()].logout;
  container.innerHTML = `<span>${escape(user.name)}</span><small>${escape(user.role)}</small><button id="logout" type="button" aria-label="${logoutLabel}" title="${logoutLabel}"><svg class="cc-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="/static/craftcontrol-ui.svg?v=7#ui-logout"></use></svg><span>${logoutLabel}</span></button>`;
  document.querySelector("#logout").onclick = async () => { await api("/api/auth/logout", { method: "POST" }); window.location.reload(); };
}

function showAuth() {
  const words = copy[locale()];
  const overlay = document.querySelector("#auth-overlay");
  overlay.hidden = false;
  const render = (mode) => {
    const claim = mode === "claim";
    const form = claim
      ? `<form id="claim-form"><label>${words.player}<input name="player" autocomplete="username" required></label><label>${words.token}<input name="token" autocomplete="one-time-code" required></label><label>${words.choose}${passwordInput(words, "new-password", 'minlength="8"')}</label><p class="auth-error" role="alert"></p><button class="primary" type="submit">${words.activate}</button><p class="auth-switch"><button id="show-login" class="auth-route-action" type="button"><span aria-hidden="true">←</span>${words.back}</button></p></form>`
      : `<form id="login-form"><label>${words.player}<input name="player" autocomplete="username" required></label><label>${words.password}${passwordInput(words, "current-password")}</label><p class="auth-error" role="alert"></p><button class="primary" type="submit">${words.login}</button><p class="auth-switch"><span>${words.noAccount}</span><button id="show-claim" class="auth-route-action" type="button">${words.claim}<span aria-hidden="true">→</span></button></p></form>`;
    overlay.innerHTML = `<section class="auth-card block-panel"><img src="/static/craftcontrol-mark.svg" alt=""><span class="eyebrow">CRAFTCONTROL</span><h1>${claim ? words.claimTitle : words.title}</h1>${form}</section>`;
    const activeForm = overlay.querySelector("form");
    activeForm.onsubmit = (event) => submit(event, claim ? "/api/auth/claim" : "/api/auth/login");
    const switcher = overlay.querySelector(claim ? "#show-login" : "#show-claim");
    switcher.onclick = () => {
      const next = claim ? "login" : "claim";
      window.history.replaceState(null, "", claim ? "#/login" : "#/first-access");
      render(next);
      overlay.querySelector("input").focus();
    };
    overlay.querySelector(".password-toggle").onclick = (event) => {
      const button = event.currentTarget;
      const input = button.parentElement.querySelector("input");
      const visible = input.type === "password";
      input.type = visible ? "text" : "password";
      button.setAttribute("aria-pressed", String(visible));
      button.setAttribute("aria-label", visible ? words.hidePassword : words.showPassword);
      button.title = visible ? words.hidePassword : words.showPassword;
    };
  };
  render(window.location.hash === "#/first-access" ? "claim" : "login");
}

async function submit(event, endpoint) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type=submit]");
  const errorBox = form.querySelector(".auth-error");
  button.disabled = true;
  errorBox.textContent = "";
  try {
    await api(endpoint, { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    window.location.reload();
  } catch (error) { errorBox.textContent = error.message; button.disabled = false; }
}

function escape(value) { const element = document.createElement("span"); element.textContent = String(value ?? ""); return element.innerHTML; }
