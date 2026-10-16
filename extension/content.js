// Rapido - bouton "Télécharger cette vidéo" qui apparaît au survol des vidéos
(() => {
  if (window.__rapido) return;
  window.__rapido = true;

  const MIN_W = 240, MIN_H = 135;
  let current = null, hideTimer = null;

  // Le bouton vit dans un Shadow DOM : le CSS du site ne peut pas le casser
  const host = document.createElement("div");
  host.style.cssText = "position:fixed;z-index:2147483647;top:0;left:0;display:none";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
    <style>
      button{all:initial;display:flex;align-items:center;gap:7px;cursor:pointer;
        font:600 13px/1 "Segoe UI",system-ui,sans-serif;color:#fff;background:#1f6f5c;
        padding:8px 12px 8px 10px;border-radius:7px;box-shadow:0 3px 12px rgba(0,0,0,.35);
        border:1px solid rgba(255,255,255,.18);transition:background .15s}
      button:hover{background:#18594a}
      svg{width:16px;height:16px;stroke:#fff;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
      .x{margin-left:4px;opacity:.7;font-weight:400;padding:0 2px}
      .x:hover{opacity:1}
    </style>
    <button id="b" title="Envoyer la vidéo à Rapido">
      <svg viewBox="0 0 24 24"><path d="M12 4v11m-5-5 5 5 5-5M5 20h14"/></svg>
      <span id="t">Télécharger cette vidéo</span><span class="x" id="x" title="Masquer">✕</span>
    </button>`;
  const btn = root.getElementById("b"), label = root.getElementById("t");
  const dismissed = new WeakSet();

  function attach() {
    if (!host.isConnected) (document.body || document.documentElement).appendChild(host);
  }

  function place() {
    if (!current || !current.isConnected) return hide(true);
    const r = current.getBoundingClientRect();
    if (r.width < MIN_W || r.height < MIN_H || r.bottom < 0 || r.top > innerHeight) return hide(true);
    host.style.display = "block";
    const w = host.offsetWidth || 220;
    host.style.left = Math.max(4, Math.min(r.right - w - 10, innerWidth - w - 4)) + "px";
    host.style.top = Math.max(4, r.top + 10) + "px";
  }

  function show(video) {
    if (dismissed.has(video)) return;
    clearTimeout(hideTimer);
    current = video;
    attach();
    place();
  }

  function hide(now) {
    clearTimeout(hideTimer);
    const go = () => { host.style.display = "none"; current = null; label.textContent = "Télécharger cette vidéo"; btn.title = "Envoyer la vidéo à Rapido"; };
    now ? go() : (hideTimer = setTimeout(go, 2500));
  }

  function videoAt(x, y) {
    for (const v of document.querySelectorAll("video")) {
      const r = v.getBoundingClientRect();
      if (r.width >= MIN_W && r.height >= MIN_H && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return v;
    }
    return null;
  }

  // les lecteurs posent souvent des calques par-dessus la vidéo : on teste la position, pas la cible
  let raf = 0;
  document.addEventListener("mousemove", (e) => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      const v = videoAt(e.clientX, e.clientY);
      if (v) show(v);
      else if (current && !host.matches(":hover")) hide(false);
    });
  }, { passive: true });
  addEventListener("scroll", () => current && place(), { passive: true, capture: true });
  addEventListener("resize", () => current && place());
  document.addEventListener("fullscreenchange", () => setTimeout(() => current && place(), 200));
  host.addEventListener("mouseenter", () => clearTimeout(hideTimer));

  root.getElementById("x").addEventListener("click", (e) => {
    e.stopPropagation();
    if (current) dismissed.add(current);
    hide(true);
  });

  // Short button labels and longer explanations, keyed by the codes the
  // background script may return. Unknown codes fall back to "unavailable".
  const SHORT = {
    video_disabled: "Capture vidéo désactivée (bêta)",
    private: "Laissé au navigateur (privé)",
    browser_session: "Laissé au navigateur (site connecté)",
    unavailable: "Rapido injoignable",
    browser_finished: "Déjà téléchargé par le navigateur",
  };
  const LONG = {
    video_disabled: "Capture vidéo désactivée dans cette bêta pour les flux et lecteurs intégrés. Utilisez « Enregistrer la vidéo sous… » du navigateur.",
    private: "Navigation privée ou conteneur : le téléchargement reste dans le navigateur.",
    browser_session: "Site connecté : le téléchargement reste dans le navigateur pour protéger votre session.",
    unavailable: "Rapido est injoignable : vérifiez qu'il est lancé et à jour.",
    browser_finished: "Le navigateur avait déjà terminé ce téléchargement : le fichier reste dans le navigateur. Pour Rapido, utilisez le clic droit « Télécharger … avec Rapido » ou cliquez directement sur le lien du fichier.",
  };
  const known = code => Object.hasOwn(SHORT, code) ? code : "unavailable";

  btn.addEventListener("click", () => {
    if (!current) return;
    const src = current.currentSrc || current.src || "";
    label.textContent = "Envoi à Rapido…";
    try {
      chrome.runtime.sendMessage({ type: "grab-video", src }, (res) => {
        const failed = chrome.runtime.lastError || !res || !res.ok;
        if (failed) {
          const code = known(res?.code);
          label.textContent = SHORT[code];
          btn.title = LONG[code];
        } else {
          label.textContent = "Envoyé ✓";
        }
        setTimeout(() => hide(false), failed ? 4000 : 1500);
      });
    } catch {
      label.textContent = "Recharge la page";   // extension mise à jour depuis le chargement
    }
  });

  // Explanation for right-click menu actions that the extension could not complete.
  const toastHost = document.createElement("div");
  toastHost.style.cssText = "position:fixed;z-index:2147483647;top:12px;right:12px;display:none;max-width:360px";
  const toastRoot = toastHost.attachShadow({ mode: "closed" });
  toastRoot.innerHTML = `
    <style>
      div{all:initial;display:block;font:13px/1.4 "Segoe UI",system-ui,sans-serif;color:#fff;background:#7a3b10;
        padding:10px 12px;border-radius:7px;box-shadow:0 3px 12px rgba(0,0,0,.35)}
      b{font-weight:600}
    </style>
    <div role="status"><b>Rapido</b> — <span id="m"></span></div>`;
  const toastText = toastRoot.getElementById("m");
  let toastTimer = null;
  chrome.runtime.onMessage.addListener((msg, sender) => {
    if (sender.id !== chrome.runtime.id || msg?.type !== "rapido-notice") return;
    toastText.textContent = LONG[known(msg.code)];
    if (!toastHost.isConnected) (document.body || document.documentElement).appendChild(toastHost);
    toastHost.style.display = "block";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastHost.style.display = "none"; }, 6000);
  });
})();
