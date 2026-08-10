import { api } from "./api.js?v=3";

const locale = () => ["pt", "en", "es"].includes(localStorage.getItem("craftcontrol-locale")) ? localStorage.getItem("craftcontrol-locale") : "pt";
const copy = {
  pt: { title: "Entrar no CraftControl", player: "Gamertag", password: "Senha", login: "Entrar", claim: "Primeiro acesso ou convite", token: "Código de convite", choose: "Escolha uma senha com pelo menos 8 caracteres", activate: "Ativar acesso", back: "Voltar ao login", logout: "Sair", showPassword: "Mostrar senha", hidePassword: "Ocultar senha" },
  en: { title: "Sign in to CraftControl", player: "Gamertag", password: "Password", login: "Sign in", claim: "First access or invitation", token: "Invitation code", choose: "Choose a password with at least 8 characters", activate: "Activate access", back: "Back to sign in", logout: "Sign out", showPassword: "Show password", hidePassword: "Hide password" },
  es: { title: "Entrar en CraftControl", player: "Gamertag", password: "Contraseña", login: "Entrar", claim: "Primer acceso o invitación", token: "Código de invitación", choose: "Elige una contraseña de al menos 8 caracteres", activate: "Activar acceso", back: "Volver al inicio de sesión", logout: "Salir", showPassword: "Mostrar contraseña", hidePassword: "Ocultar contraseña" },
};

function passwordInput(words, autocomplete, minimum = "") {
  return `<span class="password-control"><input name="password" type="password" ${minimum} autocomplete="${autocomplete}" required><button class="password-toggle" type="button" aria-label="${words.showPassword}" title="${words.showPassword}" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><use href="/static/craftcontrol-ui.svg?v=3#ui-eye"></use></svg></button></span>`;
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
  container.innerHTML = `<span>${escape(user.name)}</span><small>${escape(user.role)}</small><button id="logout" type="button" aria-label="${logoutLabel}" title="${logoutLabel}"><svg class="cc-icon" viewBox="0 0 24 24" aria-hidden="true"><use href="/static/craftcontrol-ui.svg?v=4#ui-logout"></use></svg><span>${logoutLabel}</span></button>`;
  document.querySelector("#logout").onclick = async () => { await api("/api/auth/logout", { method: "POST" }); window.location.reload(); };
}

function showAuth() {
  const words = copy[locale()];
  const overlay = document.querySelector("#auth-overlay");
  overlay.hidden = false;
  overlay.innerHTML = `<section class="auth-card block-panel"><img src="/static/craftcontrol-mark.svg" alt=""><span class="eyebrow">CRAFTCONTROL</span><h1>${words.title}</h1>
    <form id="login-form"><label>${words.player}<input name="player" autocomplete="username" required></label><label>${words.password}${passwordInput(words, "current-password")}</label><p class="auth-error" role="alert"></p><button class="primary" type="submit">${words.login}</button><button id="show-claim" class="secondary" type="button">${words.claim}</button></form>
    <form id="claim-form" hidden><label>${words.player}<input name="player" autocomplete="username" required></label><label>${words.token}<input name="token" autocomplete="one-time-code" required></label><label>${words.choose}${passwordInput(words, "new-password", 'minlength="8"')}</label><p class="auth-error" role="alert"></p><button class="primary" type="submit">${words.activate}</button><button id="show-login" class="secondary" type="button">${words.back}</button></form></section>`;
  const login = overlay.querySelector("#login-form");
  const claim = overlay.querySelector("#claim-form");
  overlay.querySelector("#show-claim").onclick = () => { login.hidden = true; claim.hidden = false; };
  overlay.querySelector("#show-login").onclick = () => { claim.hidden = true; login.hidden = false; };
  overlay.querySelectorAll(".password-toggle").forEach((button) => button.onclick = () => {
    const input = button.parentElement.querySelector("input");
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    button.setAttribute("aria-pressed", String(visible));
    button.setAttribute("aria-label", visible ? words.hidePassword : words.showPassword);
    button.title = visible ? words.hidePassword : words.showPassword;
  });
  login.onsubmit = (event) => submit(event, "/api/auth/login");
  claim.onsubmit = (event) => submit(event, "/api/auth/claim");
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
