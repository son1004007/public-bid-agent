/** 파일 설계 계약
 * 목적: 로컬 Python API에만 접근하는 사용자 입찰검토 UI, AI 추출 초안과 수기 승인 분리.
 * 권한: 서버 localhost CSRF 검증, OAuth/로그인·실제 조달 입찰 기능 없음.
 * 보존: 입력 후 명시적 POST 시 사용자 홈 JSON 저장; 파일 원본은 업로드 후 메모리 제거.
 * 불변조건: 제안 점수를 실제 검증/수주확률로 자동 승격하지 않음.
 */
let token="",cases=[],gates=[],factors=[],active=null,operations=null,operationSections=[];
const el=id=>document.getElementById(id);
const make=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e};
const message=text=>el("message").textContent=text;
async function api(path,obj){
 const res=await fetch("/api/"+path,{method:"POST",credentials:"same-origin",
  headers:{"Content-Type":"application/json","X-Local-CSRF":token},
  body:JSON.stringify(obj)});
 const val=await res.json();if(!res.ok)throw Error(val.error||"로컬 처리 실패");
 return val;
}
async function refresh(keep=true){
 const res=await fetch("/api/state",{cache:"no-store"});if(!res.ok)throw Error("로컬 상태 로드 실패");
 const v=await res.json();token=v.csrf;cases=v.data.cases;gates=v.gates;factors=v.factors;
 if(keep&&active)active=cases.find(x=>x.id===active.id)||null;
 render();
}
function render(){
 const root=el("cases");root.replaceChildren();
 cases.forEach(c=>{const b=make("button",c.title);if(active&&active.id===c.id)b.className="active";
 b.addEventListener("click",()=>{active=c;render()});root.append(b)});
 el("intro").hidden=!!active;el("workspace").hidden=!active;
 if(!active)return;
 el("caseTitle").textContent=active.title;el("prompt").value=active.prompt;
 renderCostPlan();
 const docs=el("docs");docs.replaceChildren();
 active.documents.forEach(d=>{
   const info=d.name+" · 추출 "+d.text.length+"자"+(d.method?" · "+d.method:"");
   const li=make("li",info);docs.append(li);
   (d.warnings||[]).forEach(w=>{const warning=make("small","주의: "+w);warning.style.display="block";warning.style.color="#9c691f";li.append(warning)});
  });
 const opinions=el("opinions");opinions.replaceChildren();
 ["codex","claude"].forEach(id=>{
  const article=make("article");article.append(make("h3",id==="codex"?"Codex 의견":"Claude 의견"));
  const report=active.ai_reports[id];
  if(!report)article.append(make("p","실행 전"));
  else if(report.status==="success"){
   article.append(make("p","참여 의견: "+report.result.recommendation));
   article.append(make("p",report.result.reason||"별도 이유가 없습니다"));
   article.append(make("p","항목별 근거는 아래 입력칸의 AI 초안으로 옮겨 확인하세요."));
  }else article.append(make("p",report.status+": "+(report.error||"결과 없음")));
  opinions.append(article);
 });
 renderAiFactors();
 const adviser=active.decision_support||{};
 el("decisionSupport").replaceChildren();
 if(adviser.status){
   const h=make("strong",(adviser.title||"판단 보조") + " (법적 적격·수주확률 판단 아님)");
   const details=make("p",adviser.basis||"");
   el("decisionSupport").append(h,details);
   (adviser.flags||[]).slice(0,12).forEach(v=>{
     const x=make("p",v.name+": "+(v.evidence||"추가 근거가 필요합니다"));
     el("decisionSupport").append(x);
   });
 }else{
   el("decisionSupport").textContent="AI 분석 전입니다. 원문·자격·인력·비용 근거를 확인하세요.";
 }
 const peer=active.cross_review||{};
 if(peer.status){
   const summary=peer.status==="single_or_failed"?
     ["단독 AI 분석 (두 모델 교차검토 아님)",peer.notice||"원문 검증이 필요합니다."]:
     ["두 AI 교차검토: "+peer.status,"의견 일치 "+(peer.agreements||[]).length+"건 · 이견 "+(peer.disagreements||[]).length+"건",peer.notice||""];
   (peer.disagreements||[]).slice(0,10).forEach(d=>summary.push(d.category+" / "+d.key+" : "+JSON.stringify(Object.fromEntries((peer.participants||[]).map(p=>[p,d[p]])))));
   (peer.participants||[]).forEach(p=>{
     const critique=peer.critiques?.[p];
     summary.push(p+" 상대 의견 재검토: "+(critique?.status||"실행 안 됨")+(critique?.result?" · "+(critique.result.reason||""):""));
   });
   el("crossReview").textContent=summary.join("\n");
 }else el("crossReview").textContent="교차검토 실행 전입니다.";
 renderInputs();
 el("decision").value=active.decision;el("reason").value=active.reason;
 const gateFail=gates.filter(([key])=>active.gates[key].verified&&active.gates[key].status==="fail").map(x=>x[1]);
 const gateUnknown=gates.filter(([key])=>!active.gates[key].verified||active.gates[key].status==="unknown").length;
 const factorUnknown=factors.filter(([key])=>!active.factors[key].verified||active.factors[key].score===null).length;
 const index=gateFail.length||gateUnknown||factorUnknown?null:factors.reduce((sum,[key,_,w])=>sum+active.factors[key].score*w/5,0);
 el("review").textContent="필수 미충족: "+(gateFail.join(", ")||"확정 없음")
  +" / 미검증 Gate "+gateUnknown+"개 / 미검증 요인 "+factorUnknown+"개"
  +"\n참고 가중지표: "+(index===null?"미산출":index.toFixed(1)+"/100")
  +" (실제 수주확률 아님)\n최종 결정: "+active.decision;
}
function renderAiFactors(){
 const container=el("aiFactorsPreview");container.replaceChildren();
 const draft=active?.ai_draft;
 if(!draft || !draft.gates || !draft.factors){
  container.append(make("p","AI 분석 결과가 없습니다. AI 영향인자 추출을 실행하면 20개 값을 이곳에서 볼 수 있습니다."));
  return;
 }
 const legend=make("p","현재 표시: AI의 제안 원본 · 원문 검증 전 · 수기 입력값과 별도 · '미확인'은 0점이 아님");
 legend.className="muted";container.append(legend);
 const gateStatus={pass:"충족 제안",fail:"미충족 제안",na:"해당 없음 제안",unknown:"미확인"};
 function group(title,items,category){
  const heading=make("h3",title);container.append(heading);
  const list=make("div");list.className="grid";
  items.forEach(([key,name])=>{
   const data=(draft[category]||{})[key]||{};
   const card=make("article");card.className="item";
   const value=category==="gates"?(gateStatus[data.status]||"미확인"):
       (Number.isInteger(data.score) ? String(data.score)+" / 5점" : "미확인 (점수 없음)");
   card.append(make("strong",name+" : "+value));
   const evidence=make("p","AI가 제시한 근거: "+(data.evidence||"근거가 없습니다."));
   evidence.style.whiteSpace="pre-wrap";evidence.style.overflowWrap="anywhere";
   evidence.style.margin="8px 0 0";card.append(evidence);
   const note=make("small","출처 검증 상태: 확인 전 (AI 추출값)");
   note.style.color="#8b5c1e";card.append(note);
   list.append(card);
  });
  container.append(list);
 }
 group("필수 참가조건 8개",gates,"gates");
 group("비교 평가요인 12개",factors,"factors");
}
function renderDocumentGuide(data){
 const cards=el("guideCards"), map=el("guideVariables");
 cards.replaceChildren();map.replaceChildren();
 el("guideSafety").textContent=data.safety;
 el("guideLimits").textContent=data.limits+" "+data.missing_policy;
 const docNames=Object.fromEntries(data.documents.map(d=>[d.id,d.order+"번 "+d.name]));
 docNames[data.additional_source.id]=data.additional_source.title;
 data.documents.forEach(doc=>{
  const card=make("article");card.className="item";
  card.append(make("h3",doc.order+". "+doc.name),make("p",doc.owner+" · "+(doc.classification==="public"?"공개자료":doc.classification==="public_or_restricted"?"공개 또는 제한자료":doc.classification==="company_restricted"?"회사 기밀(전송 승인 필요)":"회사 내부자료(전송 승인 필요)")));
  card.append(make("p","어디서 찾나: "+doc.examples),make("p","추출할 정보: "+doc.purpose));
  card.append(make("p","원본을 못 넣으면: "+doc.fallback));
 if(doc.id==="business_case"&&(data.operation_sources||[]).length){card.append(make("p","회사 공통 운영자료 출처: "+data.operation_sources.map(x=>x.title+"("+x.owner+")").join(", ")));}
  const warning=make("small","주의: "+doc.caution);warning.style.color="#825519";card.append(warning);
  cards.append(card);
 });
 for(const kind of ["gate","factor"]){
  map.append(make("h3",kind==="gate"?"필수조건 8개 (충족·미충족·미확인)":"평가요인 12개 (1~5점 또는 미확인)"));
  const group=make("div");group.className="grid";
  data.variables.filter(v=>v.kind===kind).forEach(v=>{
   const card=make("article");card.className="item";
   card.append(make("strong",v.label));
   card.append(make("p","필요 문서: "+v.sources.map(id=>docNames[id]||"기타 공개자료").join(" / ")));
   card.append(make("p","없으면 확인할 질문: "+v.missing_question));
   group.append(card);
  });
  map.append(group);
 }
}
async function loadDocumentGuide(){
 try{
  const response=await fetch("/document-guide.json",{cache:"no-store"});
  if(!response.ok)throw Error("HTTP "+response.status);
  renderDocumentGuide(await response.json());
 }catch(error){
  el("guideCards").replaceChildren(make("p","문서 가이드를 불러오지 못했습니다. 앱을 새로고침하거나 로컬 서버 설치를 확인하세요."));
 }
}


function displayMoney(value){return value===null||value===undefined?"미산출":Number(value).toLocaleString("ko-KR")+"원"}
function addOperationRole(row={role:"",cost_per_mm_krw:0,available_mm:0}){
 const card=make("article");card.className="item";
 const role=make("label","직무명 (개인 실명 금지)");const roleInput=make("input");
 roleInput.dataset.opsField="role";roleInput.maxLength=60;roleInput.value=row.role;role.append(roleInput);
 const cost=make("label","직무별 1MM 월 총원가 (원, 회사 부담액)");const costInput=make("input");
 costInput.type="number";costInput.min="0";costInput.step="1";costInput.dataset.opsField="cost_per_mm_krw";costInput.value=row.cost_per_mm_krw;cost.append(costInput);
 const capacity=make("label","현재 가용 공수 (MM, 최대 2자리 소수)");const capacityInput=make("input");
 capacityInput.type="number";capacityInput.min="0";capacityInput.step=".01";capacityInput.dataset.opsField="available_mm";capacityInput.value=row.available_mm;capacity.append(capacityInput);
 const del=make("button","이 직무 삭제");del.className="btn";del.type="button";del.addEventListener("click",()=>card.remove());
 card.append(role,cost,capacity,del);el("opsRoles").append(card);
}

function renderOperatingRegisters(){
 const container=el("opsRegisters");container.replaceChildren();
 operationSections.forEach(([key,title,owner])=>{
  const data=(operations?.registers||{})[key]||{};
  const card=make("article");card.className="item";card.dataset.regKey=key;
  card.append(make("h3",title),make("p","보유·확인 담당: "+owner));
  const status=make("label","현황");
  const choice=make("select");choice.dataset.regField="status";
  [["not_collected","미수집/미확인"],["needs_refresh","갱신 필요"],["reviewed","요약·출처 확인"]].forEach(([val,label])=>{
   const op=make("option",label);op.value=val;choice.append(op);
  });
  choice.value=data.status||"not_collected";status.append(choice);
  const summary=make("label","승인된 비식별 요약 (최대 600자)");
  const area=make("textarea");area.maxLength=600;area.dataset.regField="summary";area.rows=2;area.value=data.summary||"";summary.append(area);
  const source=make("label","자료 출처/내부 관리 문서명 (기밀 경로·계정 제외)");
  const src=make("input");src.maxLength=120;src.dataset.regField="source";src.value=data.source||"";source.append(src);
  const date=make("label","최종 확인일 (YYYY-MM-DD)");
  const dateInput=make("input");dateInput.type="date";dateInput.dataset.regField="reviewed_on";dateInput.value=data.reviewed_on||"";date.append(dateInput);
  [area,src,dateInput].forEach(elem=>elem.addEventListener("input",()=>{if(choice.value==="reviewed")choice.value="needs_refresh";}));
  card.append(status,summary,source,date);container.append(card);
 });
}
function collectRegisters(){
 const result={};
 for(const card of el("opsRegisters").children){
  const field=(key)=>card.querySelector('[data-reg-field="'+key+'"]');
  result[card.dataset.regKey]={status:field("status").value,summary:field("summary").value,
    source:field("source").value,reviewed_on:field("reviewed_on").value};
 }
 return result;
}

function renderOperations(){
 el("opsRoles").replaceChildren();
 (operations?.roles||[]).forEach(addOperationRole);
 renderOperatingRegisters();
 el("opsOverhead").value=operations?.overhead_pct??0;
 el("opsReserve").value=operations?.reserve_pct??0;
 el("operationsMessage").textContent=operations?"운영정보 버전 "+operations.revision+" · 저장된 역할 "+operations.roles.length+"종 · 미입력 회사 기준단가를 임의 계산하지 않습니다.":"회사 운영정보를 불러오지 못했습니다.";
}
async function loadOperations(){
 try{
  const r=await fetch("/api/operations",{cache:"no-store"});
  if(!r.ok)throw Error("운영정보 조회 실패");
  const payload=await r.json();operations=payload.operations;operationSections=payload.sections||[];
  renderOperations();
  if(active)renderCostPlan();
 }catch(e){el("operationsMessage").textContent="운영정보 오류: "+e.message}
}
function readNumber(input,optional=false){
 const value=input.value.trim();
 if(optional&&value==="")return null;
 if(value==="")throw Error("숫자 입력이 비어 있습니다.");
 const num=Number(value);
 if(!Number.isFinite(num)||num<0)throw Error("0 이상의 숫자를 입력하세요.");
 return num;
}
function collectOperations(){
 const roles=[...el("opsRoles").children].map(card=>{
  const field=k=>card.querySelector('[data-ops-field="'+k+'"]');
  return {role:field("role").value.trim(),
   cost_per_mm_krw:readNumber(field("cost_per_mm_krw")),
   available_mm:readNumber(field("available_mm"))};
 });
 return {roles,overhead_pct:readNumber(el("opsOverhead")),reserve_pct:readNumber(el("opsReserve")),
  registers:collectRegisters()};
}
function renderCostPlan(){
 const container=el("planRows");container.replaceChildren();
 const plan=active?.cost_plan||{};
 if(!operations){
  container.append(make("p","회사 공통 운영정보 조회 후 공고별 공수를 입력할 수 있습니다."));return;
 }
 if(!operations.roles.length)container.append(make("p","위에서 회사 공통 기준 직무와 월 총원가를 먼저 등록하세요."));
 const existing=Object.fromEntries((plan.entries||[]).map(e=>[e.role,e.mm]));
 operations.roles.forEach(role=>{
  const label=make("label",role.role+" · 기준 원가 "+displayMoney(role.cost_per_mm_krw)+" / MM · 가용 "+role.available_mm+"MM");
  const input=make("input");input.type="number";input.min="0";input.step=".01";input.value=existing[role.role]??0;input.dataset.planRole=role.role;
  label.append(input);container.append(label);
 });
 for(const key of ["subcontract_krw","direct_expenses_krw","proposal_krw","proposed_supply_price_krw"]){
  const input=document.querySelector('[data-plan="'+key+'"]');
  const value=plan[key];
  input.value=value===null||value===undefined?"":String(value);
  if(key!=="proposed_supply_price_krw"&&input.value==="")input.value="0";
 }
 const estimate=active.cost_estimate;
 if(!estimate){el("costResult").textContent="예상 원가 산출 전입니다. 회사 공통 운영정보를 기준으로 계산합니다.";return;}
 const stale=estimate.operations_revision!==operations.revision;
 const lines=[
  stale?"주의: 회사 운영 기준정보 버전이 변경되었습니다. 계산을 다시 저장해야 합니다.":"적용한 운영정보 버전 "+estimate.operations_revision,
  "직접 인건비 "+displayMoney(estimate.labor_krw),
  "외주비 "+displayMoney(estimate.subcontract_krw),
  "기타 직접경비 "+displayMoney(estimate.direct_expenses_krw),
  "배부 간접비 "+displayMoney(estimate.overhead_krw),
  "위험충당액 "+displayMoney(estimate.reserve_krw),
  "제안 준비비 "+displayMoney(estimate.proposal_krw),
  "예상 총원가 "+displayMoney(estimate.total_cost_krw),
  "예상 사업이익 "+displayMoney(estimate.expected_profit_krw),
  "예상 이익률 "+(estimate.expected_margin_pct===null?"미산출":estimate.expected_margin_pct+"%"),
  ...(estimate.warnings||[]).map(w=>"주의: "+w),
  "이 값은 회계 확정값/낙찰확률/AI 자동판단이 아닙니다."
 ];
 el("costResult").textContent=lines.join("\n");
}
function collectCostPlan(){
 return {entries:[...document.querySelectorAll('[data-plan-role]')].map(input=>({role:input.dataset.planRole,mm:readNumber(input)})),
  subcontract_krw:readNumber(document.querySelector('[data-plan="subcontract_krw"]')),
  direct_expenses_krw:readNumber(document.querySelector('[data-plan="direct_expenses_krw"]')),
  proposal_krw:readNumber(document.querySelector('[data-plan="proposal_krw"]')),
  proposed_supply_price_krw:readNumber(document.querySelector('[data-plan="proposed_supply_price_krw"]'),true)};
}
el("opsAddRole").addEventListener("click",()=>addOperationRole());
el("opsSave").addEventListener("click",()=>act(async()=>{
 if(!operations)throw Error("운영정보가 로드되지 않았습니다");
 const data=await api("operations/save",{expected_revision:operations.revision,operations:collectOperations()});
 operations=data.operations;renderOperations();
 if(active)renderCostPlan();
 message("회사 운영 기준을 로컬 operations.json에 저장했습니다. Codex 전송은 수행하지 않았습니다.");
}));
el("saveCostPlan").addEventListener("click",()=>act(async()=>{
 if(!active||!operations)throw Error("공고와 회사 운영정보가 필요합니다");
 const data=await api("cost-plan",{id:active.id,expected_operations_revision:operations.revision,cost_plan:collectCostPlan()});
 active=data.case;
 cases=cases.map(c=>c.id===active.id?active:c);
 render();
 message("예상 원가와 이익을 로컬 JSON에 저장했습니다. Codex 전송·입찰 제출은 수행하지 않았습니다.");
}));

function renderInputs(){
 const gg=el("gates"),ff=el("factors");gg.replaceChildren();ff.replaceChildren();
 gates.forEach(([key,title])=>{
  const current=active.gates[key],item=make("div");item.className="item";
  item.append(make("h3",title));const layout=make("div");layout.className="item-grid";
  const st=make("label","확인 상태");const select=make("select");select.dataset.gate=key;
  [["unknown","미확인"],["pass","충족(수기)"],["fail","미충족(수기)"],["na","해당없음(원문)"]].forEach(([v,name])=>{const o=make("option",name);o.value=v;select.append(o)});
  select.value=current.status;st.append(select);
  const ev=make("label","출처·근거(원문 조항/증빙)");const input=make("input");input.maxLength=400;input.dataset.gateEvidence=key;input.value=current.evidence;ev.append(input);
  const verify=make("label","내가 확인함");verify.className="verify";const cb=make("input");cb.type="checkbox";cb.dataset.gateVerify=key;cb.checked=current.verified;verify.prepend(cb);
  [select,input].forEach(e=>e.addEventListener("input",()=>{cb.checked=false}));
  layout.append(st,ev,verify);item.append(layout);gg.append(item);
 });
 factors.forEach(([key,title,weight])=>{
  const current=active.factors[key],item=make("div");item.className="item";
  item.append(make("h3",title+" (예시 "+weight+"%)"));const layout=make("div");layout.className="item-grid";
  const st=make("label","자체 평점");const select=make("select");select.dataset.factor=key;
  [["","미확인"],["1","1 매우 낮음"],["2","2 낮음"],["3","3 보통"],["4","4 높음"],["5","5 매우 높음"]].forEach(([v,name])=>{const o=make("option",name);o.value=v;select.append(o)});
  select.value=current.score===null?"":String(current.score);st.append(select);
  const ev=make("label","출처·판단 근거");const input=make("input");input.maxLength=400;input.dataset.factorEvidence=key;input.value=current.evidence;ev.append(input);
  const verify=make("label","내가 확인함");verify.className="verify";const cb=make("input");cb.type="checkbox";cb.dataset.factorVerify=key;cb.checked=current.verified;verify.prepend(cb);
  [select,input].forEach(e=>e.addEventListener("input",()=>{cb.checked=false}));
  layout.append(st,ev,verify);item.append(layout);ff.append(item);
 });
}
function collect(){
 const g={},f={};
 gates.forEach(([key])=>{g[key]={status:document.querySelector('[data-gate="'+key+'"]').value,
  evidence:document.querySelector('[data-gate-evidence="'+key+'"]').value,
  verified:document.querySelector('[data-gate-verify="'+key+'"]').checked}});
 factors.forEach(([key])=>{const v=document.querySelector('[data-factor="'+key+'"]').value;
 f[key]={score:v===""?null:Number(v),
  evidence:document.querySelector('[data-factor-evidence="'+key+'"]').value,
  verified:document.querySelector('[data-factor-verify="'+key+'"]').checked}});
 return {gates:g,factors:f};
}
async function act(action){
 try{message("");await action()}catch(e){message("오류: "+e.message)}
}
el("newCase").addEventListener("click",()=>act(async()=>{
 const title=window.prompt("검토 공고명 (민감한 고객 실명은 제외하세요)","새 입찰 검토");
 if(title===null)return;
 const v=await api("new",{title});await refresh(false);active=cases.find(c=>c.id===v.case.id);render();
}));
el("savePrompt").addEventListener("click",()=>act(async()=>{
 const v=await api("save",{id:active.id,prompt:el("prompt").value});active=v.case;render();message("설명을 내 PC JSON에 저장했습니다.");
}));
el("file").addEventListener("change",()=>act(async()=>{
 const file=el("file").files[0];if(!file)return;
 if(file.size>10*1024*1024)throw Error("파일 최대 크기는 10MiB입니다");
 const bytes=new Uint8Array(await file.arrayBuffer());
 const chunks=[];const size=24576;
 for(let i=0;i<bytes.length;i+=size){
   chunks.push(btoa(String.fromCharCode(...bytes.subarray(i,i+size))));
 }
 const v=await api("file",{id:active.id,name:file.name,base64:chunks.join("")});
 el("file").value="";active=v.case;render();const d=active.documents[active.documents.length-1];
 message("로컬 문서 추출 완료: "+(d.method||"텍스트")+". "+(d.warnings||[]).join(" / ")+" 외부 AI로 아직 전송하지 않았습니다.");
}));
el("analyze").addEventListener("click",()=>act(async()=>{
 const providers=[];if(el("codex").checked)providers.push("codex");if(el("claude").checked)providers.push("claude");
 if(!providers.length)throw Error("AI 제공자를 선택하세요");
 if(!el("consent").checked)throw Error("AI 제공자에게 전송 동의 후 실행해 주세요");
 message("분석 요청 중... 설치/로그인된 로컬 CLI에 선택 문서를 보내고 있습니다.");
 const saved=await api("save",{id:active.id,prompt:el("prompt").value});
 active=saved.case;
 const v=await api("analyze",{id:active.id,providers,consent:true});
 active=v.case;render();
 const ok=providers.filter(p=>active.ai_reports?.[p]?.status==="success");
 message(ok.length===0?"선택한 AI의 분석이 실패했습니다. 모델별 오류를 확인하세요.":
  providers.length===1?"Codex 단독 분석 완료: 원문·증빙을 확인한 뒤 초안을 적용하세요. 교차검토는 수행하지 않았습니다.":
  "분석 완료: 모델별 의견과 이견을 확인하세요. 사용자 최종 결정은 별도입니다.");
}));
el("adopt").addEventListener("click",()=>act(async()=>{
 const draft=active.ai_draft;if(!draft||!draft.gates)throw Error("적용할 AI 초안이 없습니다");
 const values=collect();
 gates.forEach(([key])=>{if(!values.gates[key].verified&&draft.gates[key]){
  values.gates[key]={...draft.gates[key],verified:false}}});
 factors.forEach(([key])=>{if(!values.factors[key].verified&&draft.factors[key]){
  values.factors[key]={...draft.factors[key],verified:false}}});
 const v=await api("save",{id:active.id,...values});active=v.case;render();
 message("AI 초안을 미검증 값으로 적용했습니다. 수정 후 원문을 확인한 항목만 체크하세요.");
}));
el("saveFactors").addEventListener("click",()=>act(async()=>{
 const v=await api("save",{id:active.id,...collect(),prompt:el("prompt").value});
 active=v.case;render();message("수정한 영향인자와 근거를 로컬 JSON에 저장했습니다.");
}));
el("decide").addEventListener("click",()=>act(async()=>{
 const values=collect();const saved=await api("save",{id:active.id,...values,prompt:el("prompt").value});
 active=saved.case;
 const v=await api("decide",{id:active.id,decision:el("decision").value,reason:el("reason").value});
 active=v.case;render();message("사용자의 최종 결정을 로컬 JSON에 기록했습니다. 입찰 제출/계약은 하지 않았습니다.");
}));
loadDocumentGuide();
loadOperations();
refresh().catch(e=>message("초기화 오류: "+e.message));