"use strict";
const status = document.querySelector("#status");

// Name the browser the user is actually in (the same extension ships for
// Chrome, Edge and Firefox).
function browserName() {
  if (location.protocol === "moz-extension:") return "Firefox";
  const brands = (navigator.userAgentData?.brands || []).map(b => b.brand);
  if (brands.some(b => /Microsoft Edge/i.test(b)) || /\bEdg\//.test(navigator.userAgent)) return "Edge";
  return "Chrome";
}
const BROWSER = browserName();
document.querySelector("#title").textContent = `Rapido — ${BROWSER} ↔ Windows`;
document.querySelector("#test").addEventListener("click", async () => {
  status.textContent = "Test en cours…";
  try {
    const result = await chrome.runtime.sendMessage({type:"rapido_native_ping"});
    status.textContent = result?.connected
      ? "Connecté : le pont natif Rapido a répondu pong (protocole 1)."
      : "Non connecté : vérifiez que Rapido est installé et que l'extension est à jour.";
  } catch {
    status.textContent = "Non connecté : communication avec l'extension indisponible.";
  }
});

const toggle = document.querySelector("#toggle");
const captureStatus = document.querySelector("#captureStatus");
async function renderCaptureState() {
  const {enabled} = await chrome.storage.local.get({enabled:true});
  toggle.textContent = enabled ? "Désactiver la capture" : "Activer la capture";
  captureStatus.textContent = `Capture ${BROWSER} ${enabled ? "activée" : "désactivée"}`;
}
toggle.addEventListener("click", async () => {
  const {enabled} = await chrome.storage.local.get({enabled:true});
  await chrome.storage.local.set({enabled:!enabled});
  await chrome.runtime.sendMessage({type:"rapido_capture_state_changed"});
  await renderCaptureState();
});
renderCaptureState();
