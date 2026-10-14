"use strict";
const BASE = "__BASE__";
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
const out=document.querySelector("#result");
document.querySelector("#start").onclick=async()=>{
  try {
    const caps=await chrome.runtime.sendNativeMessage("com.rapido.bridge",{type:"capabilities"});
    if(caps?.protocol!==1 || !caps.features?.includes("capture_handoff")) throw new Error("Verified handoff missing");
    const prepared=await chrome.runtime.sendNativeMessage("com.rapido.bridge",{
      type:"capture_prepare",url:BASE+"/probe.zip",referrer:null,filename:"probe.zip"});
    if(prepared?.type!=="capture_prepared") throw new Error("Native prepare failed");
    const aborted=await chrome.runtime.sendNativeMessage("com.rapido.bridge",{type:"capture_abort",ticket:prepared.ticket});
    if(aborted?.ok!==true) throw new Error("Native abort failed");
    const id=await chrome.downloads.download({url:BASE+"/automatic.zip",filename:"automatic.zip",saveAs:false});
    await until(async()=> {
      const rows=await search(id);
      if(rows[0]?.state==="complete") throw new Error("Automatic capture stayed in Firefox");
      return rows.length===0;
    });
    out.textContent=JSON.stringify({ok:true,verified_native:true,automatic_handoff:true});
  } catch(error) {
    out.textContent=JSON.stringify({ok:false,error:String(error)});
  }
  out.dataset.done="true";
};
document.querySelector("#fallback").onclick=async()=>{
  out.dataset.done="false";
  try {
    const id=await chrome.downloads.download({url:BASE+"/fallback.zip",filename:"fallback.zip",saveAs:false});
    await until(async()=> (await search(id))[0]?.state==="complete");
    out.textContent=JSON.stringify({ok:true,host_absent_keeps_browser_download:true});
  } catch(error) {
    out.textContent=JSON.stringify({ok:false,error:String(error)});
  }
  out.dataset.done="true";
};
