/** BID-03 합성 UI 계약: 임시 DOM/응답만 사용. 조회·오류·경쟁·오인 방지 검증. */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/public/dashboard-live.js'),'utf8');
const fragment=source.split('// BID03_START:')[1].split('\n').slice(1).join('\n').split('// BID03_END')[0];
const id='G2B-SYNTH-0001';
function payload() {
  const row={id,status:'NEEDS_EXTRACTION_REVIEW',bidding_window:'OPEN',document_state:'EXTRACTED_TEXT',
    reason_codes:['STORED_EXTRACTION_QUALITY_UNVERIFIED'],document_quality_flags:['PARSER_TRUNCATION_REPORTED'],
    legal_eligibility:'UNVERIFIED',profit_after_augmentation_cost:'UNVERIFIED',augmentation_feasibility:'UNVERIFIED',bid_decision:'HUMAN_ONLY'};
  return {storage:'LOCAL_READ_ONLY',dashboard_revision:1,shortlist:{
    mode:'READ_ONLY_BID_OPPORTUNITY_REVIEW_NOT_ELIGIBILITY',snapshot_time:'2026-10-19T12:00:00+09:00',
    total_notices:28,per_bucket_limit:20,legal_eligibility:'UNVERIFIED',profitability:'UNVERIFIED',
    human_review_required:true,automatic_bid_submittal:false,private_operations_data_included:false,
    status_counts:{HOLD_OFFICIAL_STATUS:2,HOLD_DEADLINE:3,HOLD_STALE_DOCUMENT:1},
    matching_total:21,matching_results:[row],augmentation_review_total:1,
    augmentation_review_results:[{...row,id:'G2B-SYNTH-0002',status:'CAPABILITY_GAP_MARGIN_REVIEW'}],
    registration_review_total:0,registration_review_results:[]}};
}
class Element {
  constructor(tag,cls='',text=''){this.tag=tag;this.className=cls;this.textContent=text;this.children=[];this.dataset={};this.listeners={};this.attributes={};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=[...items];}
  addEventListener(name,fn){this.listeners[name]=fn;}
  setAttribute(k,v){this.attributes[k]=v;}
  get options(){return this.children;}
  get value(){return this._value ?? (this.tag==='select'?this.children[0]?.value:'');}
  set value(v){this._value=v;}
  text(){return [this.textContent,...this.children.map(x=>x.text())].join(' ');}
  find(pred){if(pred(this))return this;for(const c of this.children){const r=c.find(pred);if(r)return r;}}
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function harness(fetcher) {
  const root=new Element('main'),nav=new Element('nav'),breadcrumb=new Element('strong');
  breadcrumb.id='breadcrumb';
  root.append(nav,breadcrumb);const calls=[],opened=[],timers=new Map();let tid=0,reloads=0;
  const byId=id=>root.find(e=>e.id===id);
  const context={el:(...a)=>new Element(...a),btn:(label,fn)=>{const e=new Element('button','btn',label);e.addEventListener('click',fn);return e;},
    byId,document:{querySelector:selector=>selector==='.nav'?nav:root},
    show:()=>{},fetch:(url,options)=>{calls.push({url,options});return fetcher(url,options);},
    AbortController,Date,Number,Error,setTimeout:fn=>{timers.set(++tid,fn);return tid;},clearTimeout:id=>timers.delete(id),
    revision:1,notices:[{id}],openFullDetail:id=>opened.push(id),reload:async()=>{reloads++;},
  };
  vm.runInNewContext(fragment,context);
  return {root,nav,context,calls,opened,timers,byId,reloads:()=>reloads,
    enter:()=>nav.children[0].listeners.click(),refresh:()=>byId('bidNowRefresh').listeners.click(),
    choose:value=>{byId('bidNowQueue').value=value;byId('bidNowQueue').listeners.change();},
    detail:()=>byId('bidNowRows').find(e=>e.tag==='button').listeners.click()};
}
const response=(body=payload())=>({ok:true,status:200,json:async()=>body});

test('three queues, counts/limit/omissions, grouped holds, explicit unknowns and GET only',async()=>{
  const h=harness(async()=>response());h.enter();await flush();
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].url,'/api/dashboard/bid-now-shortlist');
  assert.equal(h.calls[0].options.method,undefined);assert.equal(h.calls[0].options.cache,'no-store');
  assert.equal(h.byId('bidNowQueue').options.length,3);
  assert.match(h.byId('bidNowStatus').text(),/총 21건 \/ 표시 1건 \/ 미표시 20건/);
  assert.match(h.byId('bidNowHeld').text(),/취소·구차수·공식 상태 확인 보류 2건/);
  assert.match(h.root.text(),/법적 적격 미검증 \(UNVERIFIED\)/);
  assert.match(h.byId('bidNowRows').text(),/텍스트 잘림 보고/);
  h.choose('augmentation_review_results');assert.match(h.byId('bidNowRows').text(),/보완 후 마진 UNVERIFIED/);
  h.choose('registration_review_results');assert.match(h.byId('bidNowRows').text(),/표시할 후보가 없습니다/);
  assert.equal(h.calls.length,1);
});
test('existing detail opens only current snapshot identity',async()=>{
  const h=harness(async()=>response());h.enter();await flush();h.detail();assert.deepEqual(h.opened,[id]);
});
for(const stale of ['missing','revision']) test(`stale detail ${stale} refreshes without opening`,async()=>{
  const h=harness(async()=>response());h.enter();await flush();
  if(stale==='missing')h.context.notices=[];else h.context.revision=2;
  h.detail();await flush();assert.deepEqual(h.opened,[]);assert.equal(h.reloads(),1);
});
for(const status of [403,503]) test(`HTTP ${status} clears previous rows, hides raw private error`,async()=>{
  let fail=false;const h=harness(async()=>fail?{ok:false,status,json:async()=>({error:'PRIVATE_SECRET'})}:response());
  h.enter();await flush();fail=true;h.refresh();await flush();
  assert.equal(h.byId('bidNowRows').children.length,0);assert.doesNotMatch(h.root.text(),/PRIVATE_SECRET/);
  assert.match(h.byId('bidNowStatus').text(),status===403?/접근이 거절/:/0건으로 판정하지 않습니다/);
});
test('malformed schema or forged verified state is an error, never zero results',async()=>{
  for(const mutate of [p=>p.storage='OTHER',p=>p.shortlist.matching_results=null,
    p=>p.shortlist.matching_total=-1,p=>p.shortlist.matching_results[0].legal_eligibility='VERIFIED',
    p=>p.shortlist.matching_results[0].id='<img onerror=x>',p=>p.shortlist.snapshot_time='bad']) {
    const p=payload();mutate(p);const h=harness(async()=>response(p));h.enter();await flush();
    assert.equal(h.byId('bidNowRows').children.length,0);assert.match(h.byId('bidNowStatus').text(),/응답 형식 오류/);
  }
});
test('unknown/HTML codes use fixed text; private extra properties are ignored',async()=>{
  const p=payload();p.shortlist.matching_results[0].status='<img src=x onerror=evil>';
  p.shortlist.matching_results[0].private_cost='PRIVATE_SECRET';
  const h=harness(async()=>response(p));h.enter();await flush();
  assert.match(h.byId('bidNowRows').text(),/미확인 상태/);assert.doesNotMatch(h.root.text(),/onerror|PRIVATE_SECRET/);
});
test('late response cannot overwrite newer snapshot',async()=>{
  let resolve;let calls=0;const h=harness(()=>++calls===1?new Promise(r=>resolve=r):Promise.resolve(response()));
  h.enter();h.refresh();await flush();const text=h.byId('bidNowStatus').text();
  resolve({ok:false,status:503});await flush();assert.equal(h.byId('bidNowStatus').text(),text);
  assert.equal(h.calls[0].options.signal.aborted,true);
});
test('timeout aborts GET and provides retry with no results',async()=>{
  const h=harness((url,opts)=>new Promise((resolve,reject)=>opts.signal.addEventListener('abort',()=>reject(Error('aborted')))));
  h.enter();[...h.timers.values()][0]();await flush();
  assert.match(h.byId('bidNowStatus').text(),/시간 초과/);assert.equal(h.byId('bidNowRows').children.length,0);
  assert.equal(h.byId('view-bid-now').attributes['aria-busy'],'false');
});
test('empty snapshot succeeds; invalid JSON and network errors remain errors',async()=>{
  const p=payload();p.shortlist.total_notices=0;p.shortlist.status_counts={};
  for(const key of ['matching','augmentation_review','registration_review']) {
    p.shortlist[key+'_total']=0;p.shortlist[key+'_results']=[];
  }
  const h=harness(async()=>response(p));h.enter();await flush();
  assert.match(h.byId('bidNowStatus').text(),/전체 0건/);assert.match(h.byId('bidNowRows').text(),/표시할 후보가 없습니다/);
  for(const fetcher of [async()=>{throw Error('PRIVATE_NETWORK_ERROR');},
    async()=>({ok:true,json:async()=>{throw Error('PRIVATE_JSON_ERROR');}})]) {
    const failed=harness(fetcher);failed.enter();await flush();
    assert.match(failed.byId('bidNowStatus').text(),/조회 실패/);assert.doesNotMatch(failed.root.text(),/PRIVATE_/);
  }
});
