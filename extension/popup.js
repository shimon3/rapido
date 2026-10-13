"use strict";
const status = document.querySelector("#status");
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
  captureStatus.textContent = enabled ? "Capture Chrome activée" : "Capture Chrome désactivée";
}
toggle.addEventListener("click", async () => {
  const {enabled} = await chrome.storage.local.get({enabled:true});
  await chrome.storage.local.set({enabled:!enabled});
  await chrome.runtime.sendMessage({type:"rapido_capture_state_changed"});
  await renderCaptureState();
});
renderCaptureState();
