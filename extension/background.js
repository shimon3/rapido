// Rapido - extension Chrome
// 1. Intercepte les téléchargements de Chrome (selon les types de fichiers choisis dans Rapido)
// 2. Détecte les flux vidéo des pages (m3u8, mpd, mp4...) pour le bouton "Télécharger cette vidéo"
// 3. Menu clic droit "Télécharger avec Rapido"
// Si le serveur ne répond pas, Chrome reprend la main.

const SERVER = "http://127.0.0.1:9614";
const bypass = new Set();        // URLs relancées dans Chrome par nous (à ne pas recapturer)
let cfg = {                      // copie locale des réglages Rapido (mise à jour au démarrage)
  capture_exts: ["zip","rar","7z","iso","exe","msi","mp4","mkv","avi","mov","mp3","flac","pdf","apk","dmg","gz","tar"],
  min_capture_kb: 512,
};

/* Native Messaging is optional until S2/S3 is fully migrated.
   No cookies, downloads or secrets traverse this diagnostic channel. */
const NATIVE_HOST = "com.rapido.bridge";
async function probeNativeBridge(){
  try {
    const reply = await chrome.runtime.sendNativeMessage(NATIVE_HOST, {type:"ping"});
    return reply && reply.type === "pong" && reply.protocol === 1;
  } catch (_error) {
    return false; // Older Rapido installations have no registered native host.
  }
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Only our own extension popup, not content scripts or web pages, may request diagnostics.
  if(message?.type !== "rapido_native_ping" || sender.id !== chrome.runtime.id ||
     !sender.url?.startsWith(chrome.runtime.getURL("popup.html"))) return false;
  probeNativeBridge().then(connected => sendResponse({connected}), () => sendResponse({connected:false}));
  return true;
});

/* ---------- réglages ---------- */
async function loadCfg() {
  try {
    const r = await fetch(`${SERVER}/api/settings`);
    if (r.ok) {
      const s = await r.json();
      cfg = { capture_exts: s.capture_exts, min_capture_kb: s.min_capture_kb };
      await chrome.storage.local.set({ cfg });
    }
  } catch {
    const { cfg: saved } = await chrome.storage.local.get("cfg");
    if (saved) cfg = saved;
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

/* ---------- échanges avec le serveur ---------- */
async function cookieHeader(url) {
  try {
    const cookies = await chrome.cookies.getAll({ url });
    return cookies.map(c => `${c.name}=${c.value}`).join("; ");
  } catch { return ""; }
}
async function buildHeaders(url, referrer) {
  const h = {};
  const c = await cookieHeader(url);
  if (c) h.Cookie = c;
  if (referrer) h.Referer = referrer;
  h["User-Agent"] = navigator.userAgent;
  return h;
}
async function post(path, body) {
  const r = await fetch(SERVER + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`Rapido a répondu ${r.status}`);
  return r.json();
}
// Les fenêtres (capture, progression) sont ouvertes par Rapido lui-même :
// ce sont de vraies fenêtres Windows, même quand on clique depuis Chrome.
async function captureFile(url, referrer, filename) {
  await post("/api/capture", { url, filename, headers: await buildHeaders(url, referrer), open_window: true });
  flash("✓", "#1f6f5c");
}

async function captureVideo(pageUrl, candidates, referrer) {
  await post("/api/capture-video", {
    page_url: pageUrl, candidates, headers: await buildHeaders(pageUrl, referrer), open_window: true,
  });
  flash("✓", "#1f6f5c");
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
  ext = ext || MIME_EXT[(item.mime || "").split(";")[0]] || "";
  if (ext) handleDownload(item, ext);
});
// …2e essai quand Chrome connaît le vrai nom du fichier (liens du type /download?id=123)
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  suggest();
  handleDownload(item, extOf((item.filename || "").split(/[\\/]/).pop()));
});

async function handleDownload(item, ext) {
  if (handled.has(item.id)) return;
  const url = item.finalUrl || item.url;
  if (!/^https?:/i.test(url)) return;                 // blob:, data: -> Chrome s'en charge
  if (bypass.has(url)) { handled.add(item.id); bypass.delete(url); return; }
  if (!ext || !cfg.capture_exts.includes(ext)) return;
  if (!(await isEnabled())) return;
  const size = item.totalBytes || item.fileSize || 0;
  if (size > 0 && size < cfg.min_capture_kb * 1024) return;
  if (handled.has(item.id)) return;
  handled.add(item.id);

  try { await chrome.downloads.cancel(item.id); } catch {}
  try { await chrome.downloads.erase({ id: item.id }); } catch {}

  const name = (item.filename || "").split(/[\\/]/).pop();
  try {
    await captureFile(url, item.referrer, name || undefined);
  } catch (e) {
    console.warn("Rapido injoignable, téléchargement relancé dans Chrome", e);
    bypass.add(url);
    chrome.downloads.download({ url });
    flash("!", "#b4541a");
  }
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
  if (d.tabId < 0) return;
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
    grabVideo(sender.tab, sender.url, msg.src)
      .then(() => reply({ ok: true }))
      .catch(e => reply({ ok: false, error: String(e) }));
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
  try {
    if (info.menuItemId === "rapido-link") {
      const url = info.linkUrl || info.srcUrl;
      if (url && /^https?:/i.test(url)) await captureFile(url, info.pageUrl || tab?.url);
    } else if (info.menuItemId === "rapido-video" && tab) {
      await grabVideo(tab, info.frameUrl, info.srcUrl);
    }
  } catch {
    flash("!", "#b4541a");
  }
});

/* clic sur l'icône = activer / désactiver la capture */
chrome.action.onClicked.addListener(async () => {
  await chrome.storage.local.set({ enabled: !(await isEnabled()) });
  updateBadge();
  loadCfg();
});
