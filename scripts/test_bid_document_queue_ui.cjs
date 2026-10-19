/** BID-05 합성 UI 계약: 공식 미검증·작업/보류·비동기 경합·고정 오류·GET만 검증한다. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/public/dashboard-live.js'),'utf8');
const fragment=source.split('// BID05_START:')[1].split('\n').slice(1).join('\n').split('// BID05_END')[0];
class Element{
 constructor(tag,cls='',text=''){this.tag=tag;this.className=cls;this.textContent=text;this.children=[];this.attributes={};this.listeners={};}
 append(...items){this.children.push(...items);}replaceChildren(...items){this.children=[...items];}
 setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,v){this.listeners[k]=v;}
 text(){return [this.textContent,...this.children.map(x=>x.text())].join(' ');}
 find(id){return this.id===id?this:this.children.map(x=>x.find(id)).find(Boolean);}
}
const flush=()=>new Promise(r=>setImmediate(r));
function payload(){
 const row={id:'G2B-BID05SYNTH-001',queue_state:'ACTION_REQUIRED',priority:'P1',deadline_bucket:'WITHIN_24H',
  effort_band:'MEDIUM_DOWNLOAD_APPROVAL',priority_reasons:['OFFICIAL_DEADLINE_ORDER','DOCUMENT_GAP_REVIEW','EFFORT_TIE_BREAK_ONLY'],
  document_state:'READY_TO_FETCH',reason_codes:['DOWNLOAD_PENDING','OFFICIAL_ORIGINAL_RECHECK'],
  official_attachment_count:1,bound_extracted_count:0,source_binding:'UNVERIFIED',reevaluation_status:'BLOCKED_SOURCE',
  can_reevaluate_stored_text:false,next_steps:['OBTAIN_ORIGINAL_AFTER_APPROVAL'],official_freshness:'UNVERIFIED',
  original_binary_sha_rechecked:false,analysis_complete:false,legal_eligibility:'UNVERIFIED',estimated_profit:'UNVERIFIED',
  staffing_and_mm:'UNVERIFIED',evidence_status:'BLOCKED_EVIDENCE'};
 return {storage:'LOCAL_READ_ONLY',queue:{schema_version:1,dashboard_revision:0,mode:'READ_ONLY_DOCUMENT_FOLLOWUP',status:'BLOCKED_EVIDENCE',
  total_notices:2,needs_attention_count:2,action_required_count:1,held_count:1,reason_counts:{DOWNLOAD_PENDING:1,CANCELLED:1},
  results:[row],held_results:[{...row,id:'G2B-BID05HELD-001',queue_state:'HELD',priority:'HOLD',reason_codes:['CANCELLED'],
    next_steps:['VERIFY_HELD_STATUS_NO_RETRY']}],omitted_count:0,held_omitted_count:0,automatic_download:false,automatic_retry:false,
  automatic_bid_submittal:false,analysis_complete:false,legal_eligibility:'UNVERIFIED',estimated_profit:'UNVERIFIED',staffing_and_mm:'UNVERIFIED',
  cannot_auto_discard_on_capability_gap:true,private_text_included:false,source_files_written:false,
  release_metadata_state:'LEGACY_COMPLETED_UNVERIFIED'}};
}
const response=(body=payload())=>({ok:true,json:async()=>body});
function harness(fetcher,options={}){
 const root=new Element('section'),calls=[],timers=new Map(),details=[],detailStates=[],notifications=[];let next=0,reloads=0;
 const byId=id=>id==='view-bid-now'?root:root.find(id);
 const context={byId,revision:0,page:'bid-now',notices:[{id:'G2B-BID05SYNTH-001',state:'CURRENT'},{id:'G2B-BID05HELD-001',state:'OLD'}],
  reload:async()=>{reloads++;if(options.reload)await options.reload(context);},notify:message=>notifications.push(message),
  el:(...a)=>new Element(...a),btn:(text,fn)=>{
  const e=new Element('button','',text);e.listeners.click=fn;return e;},openFullDetail:id=>{
   details.push(id);detailStates.push(context.notices.find(n=>n.id===id)?.state);},
  fetch:(url,opts)=>{calls.push({url,opts});return fetcher(url,opts);},AbortController,
  setTimeout:fn=>{timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id)};
 vm.runInNewContext(fragment,context);
 return {root,byId,calls,timers,details,detailStates,notifications,context,reloads:()=>reloads,
  detail:()=>byId('bidDocumentQueueRows').children[0].children.find(x=>x.tag==='button').listeners.click(),
  refresh:()=>byId('bidDocumentQueueRefresh').listeners.click()};
}
test('queue/held counts, deadline, fixed reasons, legacy warning and safe existing detail; GET only',async()=>{
 const h=harness(async()=>response());assert.equal(h.calls.length,0);h.refresh();await flush();
 assert.match(h.root.text(),/확인 필요 2건.*확인 작업 1건.*보류 1건/);
 assert.match(h.root.text(),/24시간 이내/);assert.match(h.root.text(),/문서 다운로드 대기/);
 assert.match(h.root.text(),/인력·MM UNVERIFIED/);assert.match(h.root.text(),/현재 세대 무결성 미검증/);
 h.detail();await flush();assert.equal(h.reloads(),1);
 assert.deepEqual(h.details,['G2B-BID05SYNTH-001']);
 const choose=h.byId('bidDocumentQueueKind');choose.value='held_results';choose.listeners.change();
 assert.match(h.root.text(),/공식 취소 신호 · 재시도 금지/);
 assert.equal(h.calls[0].url,'/api/dashboard/bid-document-queue');assert.equal(h.calls[0].opts.method,undefined);
});
test('HTTP403/503, network and malformed JSON clear stale rows and never echo private error',async()=>{
 for(const brokenResponse of [async()=>({ok:false,status:403}),async()=>({ok:false,status:503}),
  async()=>{throw Error('PRIVATE_NETWORK');},async()=>({ok:true,json:async()=>{throw Error('PRIVATE_JSON')}})]){
  let broken=false;const h=harness(()=>broken?brokenResponse():Promise.resolve(response()));h.refresh();await flush();
  broken=true;h.refresh();assert.equal(h.byId('bidDocumentQueueRows').children.length,0);await flush();
  assert.equal(h.byId('bidDocumentQueueRows').children.length,0);assert.doesNotMatch(h.root.text(),/PRIVATE_/);
  assert.match(h.root.text(),/접근 거절|0건으로 판단하지 않습니다/);
 }
});
test('forged completed/qualified state, counts and untrusted text fail closed',async()=>{
 for(const mutate of [q=>q.total_notices=3,q=>q.legal_eligibility='VERIFIED',q=>q.automatic_download=true,
  q=>q.results[0].reason_codes=['<img src=x onerror=bad>'],q=>q.results[0].analysis_complete=true,
  q=>q.results[0].can_reevaluate_stored_text=true]){
  const p=payload();mutate(p.queue);const h=harness(async()=>response(p));h.refresh();await flush();
  assert.match(h.root.text(),/응답 확인 실패/);assert.equal(h.byId('bidDocumentQueueRows').children.length,0);
  assert.doesNotMatch(h.root.text(),/onerror/);
 }
});
test('latest response wins; previous request cancelled',async()=>{
 let resolve,calls=0;const h=harness(()=>++calls===1?new Promise(r=>resolve=r):Promise.resolve(response()));
 h.refresh();h.refresh();await flush();const before=h.root.text();resolve({ok:false,status:503});await flush();
 assert.equal(h.root.text(),before);assert.equal(h.calls[0].opts.signal.aborted,true);
});
test('timeout ends busy state and empty queue differs from failure',async()=>{
 const h=harness((url,opts)=>new Promise((r,j)=>opts.signal.addEventListener('abort',()=>j(Error('aborted')))));
 h.refresh();[...h.timers.values()][0]();await flush();assert.match(h.root.text(),/時間|시간 초과/);
 assert.equal(h.byId('bidDocumentQueue').attributes['aria-busy'],'false');
 const p=payload();Object.assign(p.queue,{total_notices:0,needs_attention_count:0,action_required_count:0,held_count:0,
  reason_counts:{},results:[],held_results:[]});const empty=harness(async()=>response(p));empty.refresh();await flush();
 assert.match(empty.root.text(),/확인 필요 0건/);assert.match(empty.root.text(),/선택한 목록은 0건/);
});
test('same-ID stale or cancellation opens only refreshed current detail memory',async()=>{
 for(const state of ['STALE','CANCELLED']){
  const p=payload();p.queue.dashboard_revision=2;
  p.queue.held_results[0].reason_codes=[state==='STALE'?'STALE_SOURCE':'CANCELLED'];
  const h=harness(async()=>response(p),{reload:async ctx=>{
   ctx.revision=2;ctx.notices=[{id:'G2B-BID05HELD-001',state}];
  }});h.refresh();await flush();const choose=h.byId('bidDocumentQueueKind');choose.value='held_results';choose.listeners.change();
  h.detail();await flush();assert.equal(h.reloads(),1);assert.deepEqual(h.detailStates,[state]);
 }
});
test('new ID can load safely; change after queue snapshot refreshes queue without opening detail',async()=>{
 const p=payload();p.queue.dashboard_revision=1;
 const fresh=harness(async()=>response(p),{reload:async ctx=>{
  ctx.revision=1;ctx.notices=[{id:'G2B-BID05SYNTH-001',state:'NEW'}];
 }});fresh.context.notices=[];fresh.refresh();await flush();fresh.detail();await flush();
 assert.deepEqual(fresh.detailStates,['NEW']);
 let query=0;const changed=harness(async()=>response({...p,queue:{...p.queue,dashboard_revision:++query===1?1:2}}),{
  reload:async ctx=>{ctx.revision=2;ctx.notices=[{id:'G2B-BID05SYNTH-001',state:'STALE'}];}
 });changed.refresh();await flush();changed.detail();await flush();
 assert.equal(changed.details.length,0);assert.equal(changed.calls.length,2);assert.match(changed.notifications.join(' '),/변경되었습니다/);
});
test('dashboard reload failure never opens previous detail and echoes no private error',async()=>{
 const h=harness(async()=>response(),{reload:async()=>{throw Error('PRIVATE_DASHBOARD_ERROR')}});
 h.refresh();await flush();h.detail();await flush();
 assert.equal(h.details.length,0);assert.equal(h.calls.length,2);
 assert.match(h.notifications.join(' '),/이전 상세를 열지 않았습니다/);assert.doesNotMatch(h.notifications.join(' '),/PRIVATE/);
});
test('queue refresh or another detail click invalidates pending detail request without concurrent reload',async()=>{
 for(const action of ['refresh','detail','leave']){
  let resolve;const h=harness(async()=>response(),{reload:()=>new Promise(r=>resolve=r)});
  h.refresh();await flush();h.detail();await flush();
  if(action==='leave')h.context.page='notices';else h[action]();await flush();
  resolve();await flush();assert.equal(h.details.length,0);assert.equal(h.reloads(),1);assert.equal(h.calls.length,action==='leave'?1:2);
 }
});
