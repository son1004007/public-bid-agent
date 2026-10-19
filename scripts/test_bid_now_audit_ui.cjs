/** BID-04 화면 계약: 합성 응답·DOM으로 비식별 집계, 오류/0건 구별, 요청 경쟁을 검증한다. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/public/dashboard-live.js'),'utf8');
const fragment=source.split('// BID04_START:')[1].split('\n').slice(1).join('\n').split('// BID04_END')[0];
class Element {
  constructor(tag,cls='',text=''){this.tag=tag;this.textContent=text;this.children=[];this.attributes={};this.listeners={};}
  append(...items){this.children.push(...items);} replaceChildren(...items){this.children=[...items];}
  setAttribute(k,v){this.attributes[k]=v;} addEventListener(k,v){this.listeners[k]=v;}
  text(){return [this.textContent,...this.children.map(x=>x.text())].join(' ');}
  find(id){return this.id===id?this:this.children.map(x=>x.find(id)).find(Boolean);}
}
const flush=()=>new Promise(r=>setImmediate(r));
function payload(){
  const audit={schema_version:1,mode:'READ_ONLY_LOCAL_AGGREGATE',status:'BLOCKED_EVIDENCE',
    snapshot_check:'STABLE_OBSERVED_READS',source_files_written:false,private_data_included:false,
    legal_eligibility:'UNVERIFIED',profitability:'UNVERIFIED',augmentation_permitted:'UNVERIFIED',
    automatic_bid_submittal:false,bid_decision:'HUMAN_ONLY',cannot_auto_discard_on_capability_gap:true,
    evaluated_at:'2026-10-19T14:00:00+09:00',total_notices:6,active_notice_count:3,held_notice_count:3,
    invalid_notice_count:0,active_department_category_match_count:1,active_department_match_unknown_count:1,
    active_augmentation_review_count:1,active_registration_review_count:1,
    deadline_counts:{CLOSED:1,UNKNOWN:0,WITHIN_24H:2,WITHIN_72H:1,WITHIN_7D:1,LATER:1},
    active_deadline_counts:{CLOSED:0,UNKNOWN:0,WITHIN_24H:1,WITHIN_72H:1,WITHIN_7D:1,LATER:0},
    risk_counts:{CANCELLED:1,SUPERSEDED:1,STALE_DOCUMENT:1,DEADLINE_UNKNOWN:0,REGISTRATION_UNKNOWN:1,DOCUMENT_REVIEW:3},
    consistency_counts:{DUPLICATE_ID_ROWS:0,AMBIGUOUS_NUMERIC_REVISION_ROWS:0,LIFECYCLE_MISMATCH_ROWS:0,
      STORED_WINDOW_MISMATCH_ROWS:1,REGISTRATION_AFTER_CLOSE_ROWS:0},
    evidence_gap_codes:['MM_EVIDENCE_MISSING_OR_INVALID','COST_EVIDENCE_MISSING_OR_INVALID',
      'SKILLS_EVIDENCE_UNVERIFIED','<img src=x onerror=bad>'],release_metadata_state:'LEGACY_COMPLETED_UNVERIFIED'};
  return {storage:'LOCAL_READ_ONLY',audit};
}
const response=(body=payload())=>({ok:true,json:async()=>body});
function harness(fetcher){
  const root=new Element('section'),calls=[],timers=new Map();let next=0;
  const byId=id=>id==='view-bid-now'?root:root.find(id);
  vm.runInNewContext(fragment,{byId,el:(...a)=>new Element(...a),btn:(text,fn)=>{
    const e=new Element('button','',text);e.listeners.click=fn;return e;},
    fetch:(url,opts)=>{calls.push({url,opts});return fetcher(url,opts);},AbortController,
    setTimeout:fn=>{timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id)});
  return {root,byId,calls,timers,refresh:()=>byId('bidNowAuditRefresh').listeners.click()};
}
test('safe aggregate, missing evidence and legacy integrity warning; GET only',async()=>{
  const h=harness(async()=>response());h.refresh();await flush();
  assert.match(h.root.text(),/전체 저장 공고 6건/);assert.match(h.root.text(),/활성 분야 비교 불명 1건/);
  assert.match(h.root.text(),/BLOCKED_EVIDENCE/);assert.match(h.root.text(),/UNVERIFIED/);
  assert.match(h.root.text(),/현재 세대 무결성은 미검증/);
  assert.match(h.root.text(),/투입 공수\(MM\) 증빙 부족/);assert.doesNotMatch(h.root.text(),/onerror/);
  assert.equal(h.calls[0].url,'/api/dashboard/bid-now-audit');assert.equal(h.calls[0].opts.method,undefined);
});
test('403/503/invalid JSON/network failure discard results without leaking raw errors',async()=>{
  for(const failure of [async()=>({ok:false,status:403}),async()=>({ok:false,status:503}),
    async()=>({ok:true,json:async()=>{throw Error('PRIVATE_JSON');}}),async()=>{throw Error('PRIVATE_NETWORK');}]){
    let broken=false;const h=harness(()=>broken?failure():Promise.resolve(response()));
    h.refresh();await flush();broken=true;h.refresh();await flush();
    assert.equal(h.byId('bidNowAuditRows').children.length,0);assert.doesNotMatch(h.root.text(),/PRIVATE_/);
    assert.match(h.byId('bidNowAuditStatus').text(),/拒否|거절|0건으로 판단하지 않습니다/);
  }
});
test('inconsistent counts and forged verified states fail closed',async()=>{
  for(const mutate of [r=>r.total_notices=7,r=>r.legal_eligibility='VERIFIED',r=>r.risk_counts=null,
    r=>r.active_department_match_unknown_count=-1,r=>r.source_files_written=true]){
    const p=payload();mutate(p.audit);const h=harness(async()=>response(p));h.refresh();await flush();
    assert.match(h.root.text(),/응답 확인 실패/);assert.equal(h.byId('bidNowAuditRows').children.length,0);
  }
});
test('latest response wins and superseded request is aborted',async()=>{
  let resolve,calls=0;const h=harness(()=>++calls===1?new Promise(r=>resolve=r):Promise.resolve(response()));
  h.refresh();h.refresh();await flush();const before=h.root.text();resolve({ok:false,status:503});await flush();
  assert.equal(h.root.text(),before);assert.equal(h.calls[0].opts.signal.aborted,true);
});
test('timeout aborts the read and ends busy state',async()=>{
  const h=harness((url,opts)=>new Promise((r,j)=>opts.signal.addEventListener('abort',()=>j(Error('aborted')))));
  h.refresh();[...h.timers.values()][0]();await flush();
  assert.match(h.root.text(),/시간 초과/);assert.equal(h.byId('bidNowAudit').attributes['aria-busy'],'false');
});
