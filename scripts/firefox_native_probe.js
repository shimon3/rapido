"use strict";
const BASE = "__BASE__";
const CONTROL = "__CONTROL__";
const wait = ms => new Promise(resolve=>setTimeout(resolve,ms));
async function search(id) { return chrome.downloads.search({id}); }
async function until(predicate) {
  for(let n=0;n<200;n++) {
    const value=await predicate();
    if(value) return value;
    await wait(100);
  }
  throw new Error("Browser smoke timeout");
}
async function start() {
  let stage = "capabilities";
  try {
    const caps=await chrome.runtime.sendNativeMessage("com.rapido.bridge",{type:"capabilities"});
    if(caps?.protocol!==1 || !caps.features?.includes("capture_handoff")) throw new Error("Verified handoff missing");
    stage = "prepare";
    const prepared=await chrome.runtime.sendNativeMessage("com.rapido.bridge",{
      type:"capture_prepare",url:BASE+"/probe.zip",referrer:null,filename:"probe.zip"});
    if(prepared?.type!=="capture_prepared") throw new Error("Native prepare failed");
    stage = "abort";
    const aborted=await chrome.runtime.sendNativeMessage("com.rapido.bridge",{type:"capture_abort",ticket:prepared.ticket});
    if(aborted?.ok!==true) throw new Error("Native abort failed");
    stage = "automatic_download";
    const id=await chrome.downloads.download({url:BASE+"/automatic.zip",filename:"automatic.zip",saveAs:false});
    stage = "automatic_handoff";
    await until(async()=> {
      const rows=await search(id);
      if(rows[0]?.state==="complete") throw new Error("Automatic capture stayed in Firefox");
      return rows.length===0;
    });
    return {ok:true,verified_native:true,automatic_handoff:true};
  } catch(error) {
    return {ok:false,stage,error:String(error)};
  }
}
async function fallback() {
  try {
    const id=await chrome.downloads.download({url:BASE+"/fallback.zip",filename:"fallback.zip",saveAs:false});
    await until(async()=> (await search(id))[0]?.state==="complete");
    return {ok:true,host_absent_keeps_browser_download:true};
  } catch(error) {
    return {ok:false,error:String(error)};
  }
}

// This adapter exists only in the disposable test extension. The production
// background is unchanged; all native operations still use its real host/IPC.
(async () => {
  const seen = new Set();
  for (;;) {
    const command = await fetch(CONTROL + "/command", {cache:"no-store"});
    if (!command.ok) throw new Error("Probe control unavailable");
    const {phase} = await command.json();
    if ((phase === "start" || phase === "fallback") && !seen.has(phase)) {
      seen.add(phase);
      const result = await (phase === "start" ? start() : fallback());
      const report = await fetch(CONTROL + "/result", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({phase,result}),
      });
      if (!report.ok) throw new Error("Probe report refused");
      if (!result.ok || phase === "fallback") return;
    }
    await wait(100);
  }
})();
