/** 파일 설계 계약
 * 목적: 로컬 Python API에만 접근하는 사용자 입찰검토 UI, AI 추출 초안과 수기 승인 분리.
 * 권한: 서버 localhost CSRF 검증, OAuth/로그인·실제 조달 입찰 기능 없음.
 * 보존: 입력 후 명시적 POST 시 사용자 홈 JSON 저장; 파일 원본은 업로드 후 메모리 제거.
 * 불변조건: 제안 점수를 실제 검증/수주확률로 자동 승격하지 않음.
 */
let token="",cases=[],gates=[],factors=[],active=null;
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
 active=v.case;render();message("AI 응답 확인이 끝났습니다. 실패/미설치일 경우 모델별 메시지를 확인하세요. AI 제안은 아직 사람이 검증하지 않았습니다.");
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
refresh().catch(e=>message("초기화 오류: "+e.message));