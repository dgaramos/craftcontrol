import { $ } from "../core/dom.js?v=7";

let _toastTimer = null;

export function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.style.background = error ? "#ffd2cf" : "#eef8ee";
  element.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => element.classList.remove("show"), 2600);
}
