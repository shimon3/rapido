// Rapido - extension Chrome
// 1. Intercepte les téléchargements de Chrome (selon les types de fichiers choisis dans Rapido)
// 2. Détecte les flux vidéo des pages (m3u8, mpd, mp4...) pour le bouton "Télécharger cette vidéo"
// 3. Menu clic droit "Télécharger avec Rapido"
// Si le serveur ne répond pas, Chrome reprend la main.

// All browser data uses verified Native Messaging/Windows IPC; no HTTP fallback.
const bypass = new Set();        // URLs relancées dans Chrome par nous (à ne pas recapturer)
let cfg = {                      // copie locale des réglages Rapido (mise à jour au démarrage)
  capture_exts: ["zip","rar","7z","iso","exe","msi","mp4","mkv","avi","mov","mp3","flac","pdf","apk","dmg","gz","tar"],
  min_capture_kb: 512,
};

/* Native Messaging is the only browser transport. Cookies and process secrets
   never traverse extension messages. A ping alone is not capture authorization. */
const NATIVE_HOST = "com.rapido.bridge";
async function probeNativeBridge(){
  try {
    const reply = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {type:"ping"});
    return reply && reply.type === "pong" && reply.protocol === 1;
  } catch (_error) {
    return false; // Older Rapido installations have no registered native host.
  }
}
// Never treat a successful ping as authorization to transfer downloads or cookies.
async function nativeCapabilities(){
  try {
    const reply = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {type:"capabilities"});
    if(reply?.type !== "capabilities" || reply.protocol !== 1 ||
       !Array.isArray(reply.features) || reply.features.some(f => typeof f !== "string")) return [];
    return reply.features.filter(f => f === "ping" || f === "capture_public" || f === "capture_handoff");
  } catch { return []; }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Only our own extension popup, not content scripts or web pages, may request diagnostics.
  if(message?.type === "rapido_capture_state_changed" &&
     sender.id === chrome.runtime.id &&
     sender.url?.startsWith(chrome.runtime.getURL("popup.html"))) {
    updateBadge().then(() => loadCfg()).then(() => sendResponse({ok:true}));
    return true;
  }
  if(message?.type !== "rapido_native_ping" || sender.id !== chrome.runtime.id ||
     !sender.url?.startsWith(chrome.runtime.getURL("popup.html"))) return false;
  probeNativeBridge().then(connected => sendResponse({connected}), () => sendResponse({connected:false}));
  return true;
});

/* ---------- réglages ---------- */
function validCaptureConfig(s) {
  return Array.isArray(s?.capture_exts) && s.capture_exts.length <= 200 &&
    s.capture_exts.every(e => typeof e === "string" && /^[a-z0-9]{1,8}$/.test(e)) &&
    Number.isInteger(s.min_capture_kb) && s.min_capture_kb >= 0 && s.min_capture_kb <= 10000000;
}
async function loadCfg() {
  try {
    const s = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {type:"settings_public"});
    if (s?.type !== "settings_public" || !validCaptureConfig(s)) throw new Error("Configuration native indisponible");
    cfg = {capture_exts:s.capture_exts, min_capture_kb:s.min_capture_kb};
    await chrome.storage.local.set({cfg});
  } catch {
    const {cfg:saved} = await chrome.storage.local.get("cfg");
    if (validCaptureConfig(saved)) cfg = saved;
  }
}

loadCfg();

async function isEnabled() {
  const { enabled } = await chrome.storage.local.get({ enabled: true });
  return enabled;
}
async function updateBadge() {
  const on = await isEnabled();
  chrome.action.setBadgeText({ text: on ? "" : "OFF" });
  chrome.action.setBadgeBackgroundColor({ color: "#b42323" });
  chrome.action.setTitle({ title: on ? "Rapido : capture activée (clic pour désactiver)"
                                     : "Rapido : capture désactivée (clic pour activer)" });
}
function flash(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
  setTimeout(updateBadge, 2500);
}

/* Fixed, user-facing reasons. Only these codes leave the background script;
   raw error strings never reach a web page. */
const NOTICES = {
  video_disabled: "Capture vidéo désactivée dans cette bêta. Utilisez « Enregistrer la vidéo sous… » du navigateur.",
  private: "Navigation privée ou conteneur : le téléchargement reste dans le navigateur.",
  browser_session: "Site connecté : le téléchargement reste dans le navigateur pour protéger votre session.",
  unavailable: "Rapido est injoignable : vérifiez qu'il est lancé et à jour.",
  browser_finished: "Le navigateur avait déjà terminé ce téléchargement : le fichier reste dans le navigateur. Pour Rapido, cliquez directement sur le lien du fichier.",
};
function noticeError(code, message) {
  const error = new Error(message);
  error.code = code;
  return error;
}
function noticeCode(error) {
  return Object.hasOwn(NOTICES, error?.code) ? error.code : "unavailable";
}
async function notify(tab, code) {
  flash("!", "#b4541a");
  chrome.action.setTitle({ title: "Rapido : " + NOTICES[code] });
  // The content script shows the same fixed text; pages without it keep the badge/tooltip.
  try { if (tab?.id >= 0) await chrome.tabs.sendMessage?.(tab.id, { type: "rapido-notice", code }, { frameId: 0 }); }
  catch {}
}
// Download items carry no tab: explain in the tab the user is looking at.
async function notifyActive(code) {
  let tab;
  try { [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true }); } catch {}
  if (tab && browserOwnedContext(tab)) tab = undefined;   // never message a private tab
  await notify(tab, code);
}

/* ---------- échanges avec le serveur ---------- */
// S3 interim: never send Chrome cookies to the unauthenticated HTTP API.
async function buildHeaders(url, referrer) {
  const h = {};
  if (referrer) h.Referer = referrer;
  h["User-Agent"] = navigator.userAgent;
  return h;
}
function isFirefox() {
  return chrome.runtime.getURL("").startsWith("moz-extension://");
}
function browserOwnedContext(item) {
  if (item?.incognito) return true;
  const store = item?.cookieStoreId;
  // Only the ordinary Firefox jar is supported. Unknown/missing Firefox
  // context must not be mistaken for a cookie-free ordinary download.
  if (store !== undefined) return store !== "firefox-default";
  return isFirefox();
}
async function needsBrowserSession(url) {
  // A login cookie or inaccessible cookie jar means Chrome retains this download.
  try { return (await chrome.cookies.getAll(isFirefox() ? {url, storeId:"firefox-default"} : {url})).length > 0; }
  catch { return true; }
}
// Les fenêtres (capture, progression) sont ouvertes par Rapido lui-même :
// ce sont de vraies fenêtres Windows, même quand on clique depuis Chrome.
async function captureViaNative(url, referrer, filename){
  const features = await nativeCapabilities();
  if(!features.includes("capture_public")) throw new Error("Pont natif indisponible");
  const reply = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {
    type:"capture_public", url, referrer:referrer || null, filename:filename || null
  });
  if(!reply || reply.type !== "capture_result" || reply.ok !== true)
    throw new Error("Capture native refusée");
}
async function captureFile(url, referrer, filename, prepare = false) {
  // S3: context-menu captures must obey the same fail-closed session policy
  // as automatic downloads; no browser session details cross native messaging.
  if (await needsBrowserSession(url)) throw noticeError("browser_session", "Capture privée laissée à Chrome (S3)");
  if (referrer && await needsBrowserSession(referrer))
    throw noticeError("browser_session", "Page de connexion laissée à Chrome (S3)");
  // Never disclose referrer query strings or fragments (often contain session tokens).
  let safeReferrer = null;
  if (referrer) {
    const originUrl = new URL(referrer);
    if (!["http:", "https:"].includes(originUrl.protocol) ||
        originUrl.username || originUrl.password)
      throw new Error("Referrer non sécurisé (S3)");
    safeReferrer = originUrl.origin + originUrl.pathname;
  }
  if (prepare) {
    const features = await nativeCapabilities();
    if (!features.includes("capture_handoff")) throw new Error("Transfert préparé indisponible");
    const reply = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {
      type:"capture_prepare",url,referrer:safeReferrer,filename:filename || null
    });
    if (reply?.type !== "capture_prepared" || !/^[a-f0-9]{64}$/.test(reply.ticket || ""))
      throw new Error("Préparation refusée");
    return reply.ticket;
  }
  await captureViaNative(url, safeReferrer, filename);
  flash("✓", "#1f6f5c");
}

async function captureVideo(pageUrl, candidates, referrer) {
  // S3: video capture still targets an unauthenticated loopback API.
  // Never send page URLs, candidates or session-derived metadata over that path.
  // Re-enable only after the native authenticated transport is implemented.
  throw noticeError("video_disabled", "Capture vidéo temporairement désactivée : canal sécurisé requis (S3)");
}

/* ---------- interception des téléchargements ---------- */
function extOf(name) {
  const m = /\.([a-z0-9]{1,6})$/i.exec(name || "");
  return m ? m[1].toLowerCase() : "";
}

const MIME_EXT = {
  "application/zip": "zip", "application/x-zip-compressed": "zip", "application/x-rar-compressed": "rar",
  "application/vnd.rar": "rar", "application/x-7z-compressed": "7z", "application/x-msdownload": "exe",
  "application/x-msdos-program": "exe", "application/x-msi": "msi", "application/pdf": "pdf",
  "application/vnd.android.package-archive": "apk", "application/x-iso9660-image": "iso",
  "video/mp4": "mp4", "video/x-matroska": "mkv", "audio/mpeg": "mp3", "application/gzip": "gz",
};
const handled = new Set();

// 1er essai dès la création (nom pris dans l'URL ou le type MIME)…
chrome.downloads.onCreated.addListener((item) => {
  const url = item.finalUrl || item.url;
  let ext = "";
  try { ext = extOf(new URL(url).pathname); } catch {}
  ext = ext || extOf((item.filename || "").split(/[\\/]/).pop()) ||
    MIME_EXT[(item.mime || "").split(";")[0]] || "";
  if (ext) return handleDownload(item, ext);
});
// …2e essai quand Chrome connaît le vrai nom du fichier (liens du type /download?id=123)
if (chrome.downloads.onDeterminingFilename?.addListener) {
  chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
    suggest();
    handleDownload(item, extOf((item.filename || "").split(/[\\/]/).pop()));
  });
}

async function handleDownload(item, ext) {
  // Never export private-window URLs or consult the regular cookie jar for them.
  if (browserOwnedContext(item)) return;
  if (item.state === "complete" || item.state === "interrupted") return;
  if (handled.has(item.id)) return;
  const url = item.finalUrl || item.url;
  if (!/^https?:/i.test(url)) return;                 // blob:, data: -> Chrome s'en charge
  if (bypass.has(url)) { handled.add(item.id); bypass.delete(url); return; }
  if (!ext || !cfg.capture_exts.includes(ext)) return;
  if (!(await isEnabled())) return;
  const size = item.totalBytes || item.fileSize || 0;
  if (size > 0 && size < cfg.min_capture_kb * 1024) return;
  if (await needsBrowserSession(url)) return;
  if (handled.has(item.id)) return;
  handled.add(item.id);

  const name = (item.filename || "").split(/[\\/]/).pop();
  let ticket;
  try {
    // Keep the original browser request intact until Rapido acknowledges capture.
    // In particular, private referrers and missing native hosts must not cause
    // cancel/erase followed by a fresh request that loses browser session state.
    ticket = await captureFile(url, item.referrer, name || undefined, true);
  } catch {
    flash("!", "#b4541a");
    return;
  }
  let cancelled = true;
  try { await chrome.downloads.cancel(item.id); }
  catch { cancelled = false; }
  // Chromium accepts cancel() on a finished download without error: check the
  // real state so a completed file is never fetched a second time by Rapido.
  let state;
  try { state = (await chrome.downloads.search({ id: item.id }))?.[0]?.state; } catch {}
  if (!cancelled || state === "complete") {
    // A completed download or refused cancellation must retain its browser
    // history. Native acceptance alone is not proof of browser cancellation.
    try { await chrome.runtime.sendNativeMessage(NATIVE_HOST,{type:"capture_abort",ticket}); } catch {}
    await notifyActive("browser_finished");
    return;
  }
  let committed = false;
  for (let attempt=0; attempt<2 && !committed; attempt++) {
    try {
      const result=await chrome.runtime.sendNativeMessage(NATIVE_HOST,{type:"capture_commit",ticket});
      committed=result?.type === "capture_result" && result.ok === true;
    } catch {}
  }
  if (!committed) { flash("!", "#b4541a"); return; }
  flash("✓", "#1f6f5c");
  try { await chrome.downloads.erase({ id: item.id }); } catch {}
}

/* ---------- détection des flux vidéo ---------- */
const MEDIA_CT = /^(video\/|audio\/|application\/(vnd\.apple\.mpegurl|x-mpegurl|dash\+xml))/i;
const MEDIA_URL = /\.(m3u8|mpd|mp4|webm|m4v|mkv|flv|mp3|m4a)(\?|$)/i;

async function mediaFor(tabId) {
  const key = "m" + tabId;
  const o = await chrome.storage.session.get(key);
  return o[key] || [];
}

chrome.webRequest.onHeadersReceived.addListener(async (d) => {
  if (d.tabId < 0 || browserOwnedContext(d)) return;
  const ct = (d.responseHeaders || []).find(h => h.name.toLowerCase() === "content-type")?.value || "";
  if (!MEDIA_CT.test(ct) && !MEDIA_URL.test(d.url)) return;
  if (/\.(ts|m4s|aac)(\?|$)/i.test(d.url) || /seg-?\d+|chunk|range=/i.test(d.url)) return;  // morceaux d'un flux
  const isPlaylist = /mpegurl|dash\+xml/i.test(ct) || /\.(m3u8|mpd)(\?|$)/i.test(d.url);
  const key = "m" + d.tabId;
  const list = await mediaFor(d.tabId);
  if (list.some(x => x.url === d.url)) return;
  list.unshift({ url: d.url, playlist: isPlaylist, t: Date.now() });
  await chrome.storage.session.set({ [key]: list.slice(0, 15) });
}, { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other"] }, ["responseHeaders"]);

chrome.tabs.onRemoved.addListener(id => chrome.storage.session.remove("m" + id));
chrome.tabs.onUpdated.addListener((id, info) => {
  if (info.status === "loading" && info.url) chrome.storage.session.remove("m" + id);
});

async function grabVideo(tab, frameUrl, src) {
  const sniffed = await mediaFor(tab.id);
  const candidates = [];
  if (frameUrl && frameUrl !== tab.url) candidates.push(frameUrl);            // lecteur intégré (iframe)
  sniffed.filter(m => m.playlist).forEach(m => candidates.push(m.url));       // m3u8 / mpd d'abord
  if (src && /^https?:/i.test(src)) candidates.push(src);                     // <video src="...mp4">
  sniffed.filter(m => !m.playlist).forEach(m => candidates.push(m.url));
  await captureVideo(tab.url, [...new Set(candidates)], tab.url);
}

/* bouton "Télécharger cette vidéo" (content.js) */
chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg.type === "grab-video" && sender.tab) {
    if (browserOwnedContext(sender.tab)) {
      reply({ok:false,code:"private"});
      return false;
    }
    grabVideo(sender.tab, sender.url, msg.src)
      .then(() => reply({ ok: true }))
      .catch(e => reply({ ok: false, code: noticeCode(e) }));
    return true;
  }
});

/* ---------- menus clic droit ---------- */
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "rapido-link", title: "Télécharger avec Rapido", contexts: ["link", "image", "audio"] });
  chrome.contextMenus.create({ id: "rapido-video", title: "Télécharger la vidéo avec Rapido", contexts: ["video", "page", "frame"] });
  updateBadge();
});
chrome.runtime.onStartup.addListener(() => { updateBadge(); loadCfg(); });

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (browserOwnedContext(tab)) { await notify(tab, "private"); return; }
  try {
    if (info.menuItemId === "rapido-link") {
      const url = info.linkUrl || info.srcUrl;
      if (url && /^https?:/i.test(url)) await captureFile(url, info.pageUrl || tab?.url);
    } else if (info.menuItemId === "rapido-video" && tab) {
      await grabVideo(tab, info.frameUrl, info.srcUrl);
    }
  } catch (e) {
    await notify(tab, noticeCode(e));
  }
});

/* clic sur l'icône = activer / désactiver la capture */
chrome.action.onClicked.addListener(async () => {
  await chrome.storage.local.set({ enabled: !(await isEnabled()) });
  updateBadge();
  loadCfg();
});
