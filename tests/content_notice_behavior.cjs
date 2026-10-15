// Run the real content script against a minimal simulated page and check the
// texts shown for refused captures (video button and right-click notices).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "..", "extension", "content.js"), "utf8");

function element() {
  const listeners = {};
  return {
    style: {}, title: "", textContent: "", isConnected: false, offsetWidth: 200,
    addEventListener(type, fn) { listeners[type] = fn; },
    fire(type, value) { return listeners[type](value || {stopPropagation() {}}); },
    matches() { return false; },
  };
}

function page(reply, {lastError = false} = {}) {
  const nodes = [];
  const roots = [];
  let onMessage;
  const docListeners = {};
  const body = {appendChild(node) { node.isConnected = true; }};
  const document = {
    body, documentElement: body,
    createElement() {
      const host = element();
      host.attachShadow = () => {
        const ids = {};
        const root = {
          set innerHTML(html) { for (const m of html.matchAll(/id="(\w+)"/g)) ids[m[1]] = element(); },
          getElementById(id) { return ids[id]; },
        };
        roots.push(ids);
        return root;
      };
      nodes.push(host);
      return host;
    },
    addEventListener(type, fn) { docListeners[type] = fn; },
    querySelectorAll() {
      return [{getBoundingClientRect: () => ({left: 0, right: 640, top: 0, bottom: 360, width: 640, height: 360}),
               currentSrc: "https://example.org/v.mp4", isConnected: true}];
    },
  };
  const chrome = {runtime: {
    id: "rapido",
    lastError: lastError ? {message: "no receiver"} : undefined,
    sendMessage(message, callback) { assert.equal(message.type, "grab-video"); callback(reply); },
    onMessage: {addListener(fn) { onMessage = fn; }},
  }};
  const context = vm.createContext({
    window: {}, document, chrome, innerWidth: 1280, innerHeight: 720,
    addEventListener() {}, requestAnimationFrame(fn) { fn(); return 1; },
    setTimeout() { return 1; }, clearTimeout() {},
  });
  vm.runInContext(source, context);
  const [button, toast] = roots;
  return {
    hoverAndClick() {
      docListeners.mousemove({clientX: 10, clientY: 10});
      button.b.fire("click");
      return {label: button.t.textContent, title: button.b.title};
    },
    notice(message, sender = {id: "rapido"}) {
      onMessage(message, sender);
      return {text: toast.m.textContent, shown: nodes[1].style.display};
    },
  };
}

// Video capture refused by design: the button must say so, never "not running".
let shown = page({ok: false, code: "video_disabled"}).hoverAndClick();
assert.equal(shown.label, "Capture vidéo désactivée (bêta)");
assert.match(shown.title, /Enregistrer la vidéo sous/);
assert.doesNotMatch(source, /n'est pas lancé/);

shown = page({ok: false, code: "private"}).hoverAndClick();
assert.equal(shown.label, "Laissé au navigateur (privé)");

// Unknown codes, missing replies and messaging errors fall back to one honest text.
for (const [reply, options] of [[{ok: false, code: "<img src=x>"}, {}], [undefined, {}], [{ok: true}, {lastError: true}]]) {
  shown = page(reply, options).hoverAndClick();
  assert.equal(shown.label, "Rapido injoignable");
}
assert.equal(page({ok: true}).hoverAndClick().label, "Envoyé ✓");

// Right-click failures: a fixed explanation appears in the page.
const p = page({ok: true});
let toast = p.notice({type: "rapido-notice", code: "video_disabled"});
assert.equal(toast.shown, "block");
assert.match(toast.text, /Capture vidéo désactivée dans cette bêta/);
toast = p.notice({type: "rapido-notice", code: "browser_session"});
assert.match(toast.text, /Site connecté/);
toast = p.notice({type: "rapido-notice", code: "anything-else"});
assert.match(toast.text, /Rapido est injoignable/);

// Messages from another extension or of another type are ignored.
const q = page({ok: true});
assert.equal(q.notice({type: "rapido-notice", code: "private"}, {id: "other"}).shown, undefined);
assert.equal(q.notice({type: "other", code: "private"}).shown, undefined);
console.log("PASS content notices");
