const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
function setup(file){
  const html = read(file), script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  new vm.Script(script); // Parse all shipped JavaScript, not only extracted handlers.
  const nodes = {};
  const document = {activeElement:null};
  for(const id of ['confirmDialog','confirmMessage','confirmYes','confirmNo','actionError'])
    nodes['#'+id] = {onclick:null, textContent:'', hidden:true, focus(){document.activeElement=this;}};
  const dialog=nodes['#confirmDialog'];
  Object.assign(dialog, {open:false,showModal(){this.open=true;},close(){if(!this.open)return;this.open=false;setImmediate(()=>this.onclose?.());}});
  const context = vm.createContext({Promise,console,document,$:s=>nodes[s]});
  const helper = script.split('/* ---------- confirmation ---------- */')[1]
    .split(file==='index.html'?'/* ---------- utilitaires ---------- */':'/* ---------- window parameters ---------- */')[0];
  vm.runInContext(helper, context);
  return {context,nodes,dialog,script,document};
}
async function helperCases(file){
  const {context,nodes,dialog,document}=setup(file);
  const ask = message=>context.askConfirm(message);
  const text='<img src=x onerror=alert(1)> & literal';
  let first=ask(text);
  assert.equal(nodes['#confirmMessage'].textContent,text);
  assert.equal(document.activeElement,nodes['#confirmNo']);
  assert.equal(await ask('second'),false); // Must not replace the first resolver/message.
  assert.equal(nodes['#confirmMessage'].textContent,text);
  nodes['#confirmNo'].onclick(); assert.equal(await first,false);
  first=ask('Escape'); let prevented=false;
  dialog.oncancel({preventDefault(){prevented=true;}});
  assert.equal(await first,false); assert.ok(prevented);
  first=ask('external close'); dialog.close('anything'); assert.equal(await first,false);
  first=ask('confirm'); nodes['#confirmYes'].onclick(); assert.equal(await first,true);
  first=ask('reopen immediately'); nodes['#confirmNo'].onclick(); assert.equal(await first,false);
  dialog.showModal=()=>{throw Error('unsupported');}; assert.equal(await ask('failure'),false);
}
async function mainActions(){
  const {context,nodes,dialog,script}=setup('index.html');
  const calls=[], errors=[]; let release=null;
  Object.assign(context,{api:async (...args)=>{calls.push(JSON.parse(JSON.stringify(args)));if(release)await release;},refresh(){},toast:e=>errors.push(e),sel:new Set(),openWin(){}});
  vm.runInContext(script.slice(script.indexOf('let actionBusy ='),script.indexOf('/* ---------- barre d\'outils')),context);
  for(const action of ['redownload','delete','deletefile']){
    const before=calls.length;
    let item={id:'abc123',filename:'fixture',status:'paused'};
    const pending=context.act(action,[item]);
    await context.act(action,[{id:'second'}]);
    nodes['#confirmNo'].onclick(); await pending; assert.equal(calls.length,before);
    const accepted=context.act(action,[item]);
    item.id='changed-after-confirmation-opened';
    nodes['#confirmYes'].onclick(); await accepted;
    assert.equal(calls.length,before+1);
    const [url,,body]=calls.at(-1);
    if(action==='redownload') assert.equal(url,'/api/downloads/abc123/redownload');
    else {assert.equal(url,'/api/bulk/delete');assert.deepEqual(body.ids,['abc123']);assert.equal(body.delete_file,action==='deletefile');}
  }
  for(const close of [()=>dialog.oncancel({preventDefault(){}}),()=>dialog.close()]){
    const before=calls.length, pending=context.act('delete',[{id:'abc123'}]);
    close(); await pending; assert.equal(calls.length,before);
  }
  let before=calls.length,pending=context.act('resume',[{id:'abc123',status:'handoff'}]);
  nodes['#confirmNo'].onclick();await pending;assert.equal(calls.length,before);
  let releaseApi;release=new Promise(r=>releaseApi=r);
  pending=context.act('delete',[{id:'abc123'}]);nodes['#confirmYes'].onclick();await flush();
  await context.act('delete',[{id:'second'}]);assert.equal(dialog.open,false);assert.equal(calls.length,before+1);
  releaseApi();await pending;release=null;
  context.api=async()=>{throw Error('request failed');};
  pending=context.act('delete',[{id:'abc123'}]);nodes['#confirmYes'].onclick();await pending;
  assert.ok(errors.includes('request failed'));
  pending=context.act('delete',[{id:'abc123'}]);nodes['#confirmNo'].onclick();await pending; // Busy flag recovered.
}
async function popupCancellation(){
  const {context,nodes,dialog,script}=setup('window.html');
  const progress=script.slice(script.indexOf('function renderProgress'),script.indexOf('function renderDone'));
  const body=progress.split('$("#cancel").onclick = async () => {')[1].split('\n    };')[0];
  let calls=0,closed=0,fail=false;
  Object.assign(context,{ID:'abc123',closeWin(){closed++;},api:async()=>{calls++;if(fail)throw Error('pause failed');}});
  vm.runInContext('let pausedBusy=false; async function cancelProgress(){'+body+'}',context);
  for(const no of [()=>nodes['#confirmNo'].onclick(),()=>dialog.oncancel({preventDefault(){}}),()=>dialog.close()]){
    const pending=context.cancelProgress();no();await pending;assert.equal(calls,0);assert.equal(closed,0);
  }
  let pending=context.cancelProgress();await context.cancelProgress();nodes['#confirmYes'].onclick();await pending;
  assert.equal(calls,1);assert.equal(closed,1);
  fail=true;pending=context.cancelProgress();nodes['#confirmYes'].onclick();await pending;
  assert.equal(closed,1);assert.equal(nodes['#actionError'].textContent,'pause failed');assert.equal(nodes['#actionError'].hidden,false);
}
function editingShortcuts(){
  const script=setup('index.html').script;
  const source=script.slice(script.indexOf('document.addEventListener("keydown"'),script.indexOf('document.addEventListener("paste"'));
  let handler,calls=0;
  const context=vm.createContext({document:{querySelector(){return null;},addEventListener(_,fn){handler=fn;}},sel:new Set(['abc123']),act(){calls++;},selected(){return[];}});
  vm.runInContext(source,context);
  for(const editing of [true,false]){
    handler({key:'Delete',target:{closest(){return editing?{}:null;},isContentEditable:false}});
    assert.equal(calls,editing?0:1);
  }
  handler({key:'Delete',target:{closest(){return null;},isContentEditable:true}});assert.equal(calls,1);
}
(async()=>{await helperCases('index.html');await helperCases('window.html');await mainActions();await popupCancellation();editingShortcuts();console.log('Dialog behavior passed: refusal, approval, snapshots, busy guards, failures and editing shortcuts');})().catch(error=>{console.error(error);process.exitCode=1;});
