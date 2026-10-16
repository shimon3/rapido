// Run the real popup script and check it names the browser it runs in.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "..", "extension", "popup.js"), "utf8");

async function render({protocol = "chrome-extension:", userAgent = "", brands, enabled = true}) {
  const nodes = {};
  const document = {querySelector(selector) {
    return nodes[selector] || (nodes[selector] = {textContent: "", addEventListener() {}});
  }};
  const chrome = {storage: {local: {async get() { return {enabled}; }, async set() {}}},
                  runtime: {async sendMessage() { return {}; }}};
  const navigator = {userAgent, userAgentData: brands ? {brands: brands.map(brand => ({brand}))} : undefined};
  vm.runInContext(source, vm.createContext({document, chrome, navigator, location: {protocol}}));
  for (let n = 0; n < 10; n++) await new Promise(r => setImmediate(r));
  return {title: nodes["#title"].textContent, capture: nodes["#captureStatus"].textContent};
}

(async () => {
  const edgeUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36 Edg/155.0.4283.45";
  const chromeUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36";
  let shown = await render({userAgent: edgeUA, brands: ["Microsoft Edge", "Chromium", "Not.A/Brand"]});
  assert.equal(shown.title, "Rapido — Edge ↔ Windows");
  assert.equal(shown.capture, "Capture Edge activée");
  shown = await render({userAgent: edgeUA});  // no Client Hints: user agent fallback
  assert.equal(shown.capture, "Capture Edge activée");
  shown = await render({userAgent: chromeUA, brands: ["Google Chrome", "Chromium"], enabled: false});
  assert.equal(shown.title, "Rapido — Chrome ↔ Windows");
  assert.equal(shown.capture, "Capture Chrome désactivée");
  shown = await render({protocol: "moz-extension:", userAgent: "Mozilla/5.0 Firefox/158.0"});
  assert.equal(shown.capture, "Capture Firefox activée");
  // "Edge" alone in another product name must not be mistaken for Edge.
  shown = await render({userAgent: chromeUA + " KnowledgeEdg/1.0"});
  assert.equal(shown.capture, "Capture Chrome activée");
  console.log("PASS popup browser name");
})().catch(error => { console.error(error); process.exitCode = 1; });
