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
  let createdListener;
  let mediaListener;
  let cookieReads = 0;
  let mediaWrites = 0;
  let mediaReads = 0;
  const messageListeners = [];
  const firefox = mode.startsWith("firefox");
  const gate = new Promise(resolve => {release = resolve;});
  const chrome = {
    runtime: {id:"rapido", getURL:p=>(firefox ? "moz-extension://" : "chrome-extension://")+"rapido/"+p,
      onMessage:{addListener(fn){messageListeners.push(fn);}}, onInstalled:event(), onStartup:event(),
      async sendNativeMessage(host, message) {
        if (message.type === "settings_public") return {type:"settings_public",capture_exts:["zip"],min_capture_kb:512};
        calls.push(message.type);
        if (mode === "missing") throw new Error("No native host");
        if (mode === "bad-capabilities") return {type:"capabilities",protocol:999,features:["capture_public"]};
        if (message.type === "capabilities") return {type:"capabilities",protocol:1,features:["capture_public"]};
        if (mode === "pending") await gate;
        return mode === "rejected" ? {type:"error"} : {type:"capture_result",ok:true};
      }},
    storage: {local:{async get(){return {enabled:true};},async set(){}},
      session:{async get(){mediaReads++;return {};},async set(){mediaWrites++;},async remove(){}}},
    action:{setBadgeText(){},setBadgeBackgroundColor(){},setTitle(){},onClicked:event()},
    cookies:{async getAll({url,storeId}) {
      cookieReads++;
      if (firefox) assert.equal(storeId,"firefox-default");
      if (mode === "firefox-default-cookie") return [{}];
      if (mode === "cookie-error") throw new Error("Denied");
      return mode === "private-target" || (mode === "private-referrer" && url.includes("private")) ? [{}] : [];
    }},
    downloads:{onCreated:{addListener(fn){createdListener=fn;}},
      onDeterminingFilename:mode.startsWith("firefox") ? undefined : event(),
      async cancel(){calls.push("cancel");},async erase(){calls.push("erase");},
      async download(){calls.push("restart");}},
    webRequest:{onHeadersReceived:{addListener(fn){mediaListener=fn;}}}, tabs:{onRemoved:event(),onUpdated:event()},
    contextMenus:{onClicked:{addListener(fn){menuClick=fn;}},create(){}}
  };
  const context = vm.createContext({chrome, URL, navigator:{userAgent:"test"},
    async fetch(){return {ok:false};},setTimeout(){},console});
  vm.runInContext(source+"\nglobalThis.runDownload = handleDownload;", context);
  const item = {id:1,incognito:mode === "incognito",url:mode === "firefox-filename" ? "https://example.org/download" : "https://example.org/a.zip",
    referrer:"https://private.example/page",filename:"a.zip",totalBytes:1048576};
  if (firefox && mode !== "firefox-missing-store") item.cookieStoreId =
    mode.includes("container") ? "firefox-container-2" :
    mode === "firefox-private-store" ? "firefox-private" :
    mode === "firefox-unknown-store" ? "future-isolated-store" : "firefox-default";
  assert.equal(typeof createdListener, "function");
  if (mode.endsWith("video")) {
    let reply;
    const tab={id:1,url:item.url,incognito:mode==="incognito-video",cookieStoreId:item.cookieStoreId};
    for(const listener of messageListeners) {
      listener({type:"grab-video",src:item.url},{tab,url:item.url},value=>{reply=value;});
    }
    assert.equal(reply?.ok,false);
    assert.equal(mediaReads,0,"must reject private video before reading candidates");
    assert.equal(mediaWrites,0);
    assert.equal(cookieReads,0);
    assert.equal(calls.length,0);
    return;
  }
  if (mode.endsWith("media")) {
    await mediaListener({tabId:1,incognito:mode==="private-media",cookieStoreId:item.cookieStoreId,
      url:"https://example.org/private-token.mp4",responseHeaders:[{name:"content-type",value:"video/mp4"}]});
    assert.equal(mediaWrites,mode === "public-media" || mode === "firefox-public-media" ? 1 : 0,
      "only ordinary-context media may enter session storage");
    assert.equal(calls.length,0);
    return;
  }
  if (mode === "firefox-container-menu") {
    await menuClick({menuItemId:"rapido-link",linkUrl:item.url,pageUrl:item.referrer},
      {incognito:false,cookieStoreId:item.cookieStoreId,url:item.referrer});
    assert.equal(calls.length,0);
    assert.equal(cookieReads,0);
    return;
  }
  const task = mode.startsWith("firefox") ? createdListener(item) : mode === "incognito-menu" ? menuClick({menuItemId:"rapido-link",linkUrl:item.url,pageUrl:item.referrer},{incognito:true,url:item.referrer}) : context.runDownload(item, "zip");
  if (mode === "pending") {
    for(let n=0;n<20;n++) await Promise.resolve();
    assert(!calls.includes("cancel"), "must not cancel before acknowledgement");
    assert(!calls.includes("erase"));
    release();
  }
  await task;
  assert(!calls.includes("restart"), "original request must never be replaced");
  if (["missing","rejected","private-referrer","private-target","cookie-error","bad-capabilities","incognito","incognito-menu","firefox-container","firefox-private-store","firefox-missing-store","firefox-unknown-store","firefox-default-cookie"].includes(mode)) {
    assert(!calls.includes("cancel"), mode);
    assert(!calls.includes("erase"), mode);
    if (mode.startsWith("incognito") || ["firefox-container","firefox-private-store","firefox-missing-store","firefox-unknown-store"].includes(mode)) {
      assert.equal(calls.length,0);
      assert.equal(cookieReads,0);
    }
  } else {
    assert(calls.indexOf("capture_public") < calls.indexOf("cancel"));
    assert(calls.includes("erase"));
  }
}
(async()=>{
  for (const mode of ["missing","rejected","private-referrer","private-target","cookie-error","bad-capabilities","incognito","incognito-menu","pending","success","firefox-event","firefox-filename","firefox-container","firefox-container-menu","firefox-private-store","firefox-missing-store","firefox-unknown-store","firefox-default-cookie","private-media","firefox-container-media","firefox-container-video","incognito-video","public-media","firefox-public-media"]) {
    await scenario(mode);
    console.log("PASS "+mode);
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
