/** BID-06 합성 브라우저 계약: 원문 텍스트 안전 렌더, 명시 저장·보류·멱등키·최신 조회. */
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/public/rfp-ground-truth.js'),'utf8');
class Element{
 constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.listeners={};this.style={};this.attributes={};this.className='';this.classList={add:()=>{}};this.checked=false;}
 append(...xs){for(const x of xs){x.parent=this;this.children.push(x);}}
 replaceChildren(...xs){this.children=[];this.append(...xs);}addEventListener(k,f){this.listeners[k]=f;}
 setAttribute(k,v){this.attributes[k]=v;}remove(){this.parent.children=this.parent.children.filter(x=>x!==this);}
 all(){return [this,...this.children.flatMap(x=>x.all())];}text(){return this.all().map(x=>x.textContent).join(' ');}
}
const flush=()=>new Promise(r=>setImmediate(r));
const metrics={tp:null,fp:null,fn:null,precision:null,recall:null,f1:null,miss_rate:null};
function response(){const ctx={id:'G2B-BID06SYNTH-001',title:'<img src=x onerror=bad>',bid_no:'BID06SYNTH',bid_order:'001',version_key:'a'.repeat(64),blocked:false,
 documents:[{identity:'b'.repeat(64),source_sha256:'c'.repeat(64),fulltext_ref:'d'.repeat(64),name:'synthetic.txt',official_url:'https://www.g2b.go.kr/doc.txt',text:'참가자격: 합성 회사 등록',binding:'VERSION_MATCHED',truncated:true,parser_warnings_present:true}],
 candidates:[{identity:'b'.repeat(64),category:'participation',text:'참가자격: 합성 회사 등록',start:0,end:14}],omitted_candidate_count:3};
 return {csrf:'synthetic-token',review:{revision:0,context:ctx,scopes:[],history:[],stale_scope_count:0,evaluation:{state:'NOT_EVALUATED',approved_gold_count:0,approved_scope_count:0,metrics,by_category:{participation:metrics,evaluation:metrics,scope:metrics},by_route:{TEXT:metrics}}}};}
function harness(fetch){const window={},root=new Element('div');const calls=[];
 const context={window,document:{createElement:tag=>new Element(tag)},fetch:async(url,opts)=>{calls.push({url,opts});return fetch(url,opts);},AbortController,setTimeout,clearTimeout,crypto:require('node:crypto').webcrypto,Uint8Array,btoa:s=>Buffer.from(s,'binary').toString('base64')};
 vm.runInNewContext(source,context);const ui=window.rfpGroundTruth.mount(root,'G2B-BID06SYNTH-001');
 return {root,calls,ui,window,button:text=>root.all().find(x=>x.tag==='button'&&x.textContent===text),cls:name=>root.all().find(x=>x.className===name)};
}
const ok=body=>({ok:true,status:200,json:async()=>body});
test('NOT_EVALUATED, partial/omitted warnings, safe text and no automatic writes',async()=>{
 const h=harness(async()=>ok(response()));await h.ui.load('G2B-BID06SYNTH-001');
 assert.match(h.root.text(),/NOT_EVALUATED/);assert.match(h.root.text(),/잘림 있음/);assert.match(h.root.text(),/생략 후보 3개/);
 assert.equal(h.cls('bid06Gold'),undefined);assert.equal(h.calls.length,1);assert.equal(h.calls[0].opts.method,undefined);
 assert.equal(h.root.all().filter(x=>x.tag==='img').length,0);
 await h.button('독립 정답 승인·평가 저장').listeners.click();await flush();assert.equal(h.calls.length,1);
 assert.match(h.root.text(),/원본 SHA 대조/);
});
test('manual missing quote with page and location saves only after explicit HOLD',async()=>{
 const h=harness(async(url)=>ok(response()));await h.ui.load('G2B-BID06SYNTH-001');
 h.button('누락·정답 구절 수동 추가').listeners.click();h.cls('bid06GoldText').value='독립 원본에만 있는 누락';
 h.cls('bid06GoldLocation').value='각주 2';h.cls('bid06Location').value='본문 페이지1';
 h.button('검수 보류 저장').listeners.click();await flush();
 const call=h.calls.find(x=>x.opts.method==='POST');const p=JSON.parse(call.opts.body);
 assert.equal(p.status,'HOLD');assert.equal(p.gold[0].text,'독립 원본에만 있는 누락');assert.equal(p.gold[0].page,1);
 assert.equal(p.source_ticket,'');assert.equal(p.official_current_confirmed,false);assert.equal(call.opts.headers['X-Local-CSRF'],'synthetic-token');
});
test('same payload after unknown save failure reuses request_id; changed payload gets conflict-safe new key',async()=>{
 const h=harness(async(url,opts)=>{if(opts.method==='POST')throw Error('PRIVATE_ERROR');return ok(response());});
 await h.ui.load('G2B-BID06SYNTH-001');h.cls('bid06Location').value='합성 범위';
 h.button('검수 보류 저장').listeners.click();await flush();h.button('검수 보류 저장').listeners.click();await flush();
 let posts=h.calls.filter(c=>c.opts.method==='POST').map(c=>JSON.parse(c.opts.body));assert.equal(posts[0].request_id,posts[1].request_id);
 h.cls('bid06Location').value='변경 범위';h.button('검수 보류 저장').listeners.click();await flush();
 posts=h.calls.filter(c=>c.opts.method==='POST').map(c=>JSON.parse(c.opts.body));assert.notEqual(posts[1].request_id,posts[2].request_id);
 assert.doesNotMatch(h.root.text(),/PRIVATE_ERROR/);assert.match(h.root.text(),/입력과 기존 자료는 보존/);
});
test('cancelled source disables approval; HOLD remains available',async()=>{
 const p=response();p.review.context.blocked=true;const h=harness(async()=>ok(p));await h.ui.load('G2B-BID06SYNTH-001');
 assert.equal(h.button('독립 정답 승인·평가 저장').disabled,true);assert.notEqual(h.button('검수 보류 저장').disabled,true);
 assert.match(h.root.text(),/취소·구차수/);
});
test('older failed request cannot replace latest selection and raw errors are hidden',async()=>{
 let resolve,calls=0;const h=harness(()=>++calls===1?new Promise(r=>resolve=r):Promise.resolve(ok(response())));
 const first=h.ui.load('G2B-BID06SYNTH-001');await h.ui.load('G2B-BID06SYNTH-001');const before=h.root.text();
 resolve({ok:false,status:503});await first;assert.equal(h.root.text(),before);
 const bad=harness(async()=>{throw Error('PRIVATE_ROOT_PATH');});await bad.ui.load('G2B-BID06SYNTH-001');
 assert.match(bad.root.text(),/0건으로 판단하지 않습니다/);assert.doesNotMatch(bad.root.text(),/PRIVATE_ROOT_PATH/);
});
test('null metrics never formatted as perfect accuracy',()=>{
 const h=harness(async()=>ok(response()));assert.doesNotMatch(h.window.rfpGroundTruth.metricText(metrics),/100|0%/);
 assert.match(h.window.rfpGroundTruth.metricText({...metrics,recall:0.5} ),/50.0%/);
});
