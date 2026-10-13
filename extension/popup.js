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
