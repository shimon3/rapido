const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "..", "extension", "background.js"), "utf8");
const event = () => ({addListener() {}});
async function scenario(mode) {
  const calls = [];
  let release;
  let menuClick;
  const gate = new Promise(resolve => {release = resolve;});
  const chrome = {
    runtime: {id:"rapido", getURL:p=>"chrome-extension://rapido/"+p,
      onMessage:event(), onInstalled:event(), onStartup:event(),
      async sendNativeMessage(host, message) {
        calls.push(message.type);
        if (mode === "missing") throw new Error("No native host");
        if (mode === "bad-capabilities") return {type:"capabilities",protocol:999,features:["capture_public"]};
        if (message.type === "capabilities") return {type:"capabilities",protocol:1,features:["capture_public"]};
        if (mode === "pending") await gate;
        return mode === "rejected" ? {type:"error"} : {type:"capture_result",ok:true};
      }},
    storage: {local:{async get(){return {enabled:true};},async set(){}},
      session:{async get(){return {};},async set(){},async remove(){}}},
    action:{setBadgeText(){},setBadgeBackgroundColor(){},setTitle(){},onClicked:event()},
    cookies:{async getAll({url}) {
      if (mode === "cookie-error") throw new Error("Denied");
      return mode === "private-target" || (mode === "private-referrer" && url.includes("private")) ? [{}] : [];
    }},
    downloads:{onCreated:event(),onDeterminingFilename:event(),
      async cancel(){calls.push("cancel");},async erase(){calls.push("erase");},
      async download(){calls.push("restart");}},
    webRequest:{onHeadersReceived:event()}, tabs:{onRemoved:event(),onUpdated:event()},
    contextMenus:{onClicked:{addListener(fn){menuClick=fn;}},create(){}}
  };
  const context = vm.createContext({chrome, URL, navigator:{userAgent:"test"},
    async fetch(){return {ok:false};},setTimeout(){},console});
  vm.runInContext(source+"\nglobalThis.runDownload = handleDownload;", context);
  const item = {id:1,incognito:mode === "incognito",url:"https://example.org/a.zip",
    referrer:"https://private.example/page",filename:"a.zip",totalBytes:1048576};
  const task = mode === "incognito-menu" ? menuClick({menuItemId:"rapido-link",linkUrl:item.url,pageUrl:item.referrer},{incognito:true,url:item.referrer}) : context.runDownload(item, "zip");
  if (mode === "pending") {
    for(let n=0;n<20;n++) await Promise.resolve();
    assert(!calls.includes("cancel"), "must not cancel before acknowledgement");
    assert(!calls.includes("erase"));
    release();
  }
  await task;
  assert(!calls.includes("restart"), "original request must never be replaced");
  if (["missing","rejected","private-referrer","private-target","cookie-error","bad-capabilities","incognito","incognito-menu"].includes(mode)) {
    assert(!calls.includes("cancel"), mode);
    assert(!calls.includes("erase"), mode);
    if (mode.startsWith("incognito")) assert.equal(calls.length, 0);
  } else {
    assert(calls.indexOf("capture_public") < calls.indexOf("cancel"));
    assert(calls.includes("erase"));
  }
}
(async()=>{
  for (const mode of ["missing","rejected","private-referrer","private-target","cookie-error","bad-capabilities","incognito","incognito-menu","pending","success"]) {
    await scenario(mode);
    console.log("PASS "+mode);
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
