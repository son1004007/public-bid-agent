/**
 * 퍼블리싱 시안: 합성 입찰 목록/기준 프로필/영향인자 가중치 및 불참 이유를 브라우저 메모리에서만 관리한다.
 * 보안: inline script 금지 CSP를 유지하고 동일 출처 정적 JS로 제공한다.
 */
/**
 * 시안 파일 설계 계약
 * 목적: 수집 현황/참여 판단 프로필/영향인자 프로필/판단 이력을 조작 가능한 정적 UI로 시연.
 * 입력: 합성 공고, 화면의 사용자 클릭과 프로필 편집.
 * 출력: 화면 메모리상의 참고판단·결정 기록. 네트워크 호출/저장 없음.
 * 경계: 회사·공고 실제정보가 아니며 법적 입찰자격·수주가능성 확정 불가.
 * 불변: AI 권고와 사람 최종결정 분리, 불참 이유/사용한 두 프로필 버전 별도 보존.
 */
const byId=id=>document.getElementById(id);
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const fmt=n=>Number(n).toLocaleString('ko-KR');
const seed=[
{id:'DEMO-AI-001',title:'[합성] 공공기관 생성형 AI 업무지원 플랫폼',org:'가상 디지털진흥원',cat:'AI',budget:'3.2억',end:'10.28',fit:91,margin:24,hard:'pass',ops:false,exp:true,score:88,rec:'bid',final:null,reasons:['기술요건 부합','투입인력 및 원가 검토 예시'],checked:'10.10 09:20'},
{id:'DEMO-DA-002',title:'[합성] 데이터 수집·품질분석 체계 고도화',org:'가상 정보산업진흥원',cat:'DATA',budget:'1.8억',end:'10.30',fit:76,margin:17,hard:'unknown',ops:false,exp:true,score:76,rec:'hold',final:null,reasons:['공고상 필수 실적 증빙 미확인'],checked:'10.10 09:20'},
{id:'DEMO-AI-003',title:'[합성] 의료 AI 영상 판독 모델 개발',org:'가상 보건센터',cat:'AI',budget:'4.5억',end:'11.04',fit:31,margin:12,hard:'pass',ops:false,exp:true,score:41,rec:'no_bid',final:'no_bid',reasons:['기술 적합성 기준 미달','의료영상 모델 개발 역량 부족'],checked:'10.10 09:20'},
{id:'DEMO-DA-004',title:'[합성] 통계 데이터 분석서비스 구축',org:'가상 통계연구원',cat:'DATA',budget:'2.1억',end:'11.11',fit:84,margin:22,hard:'pass',ops:false,exp:true,score:82,rec:null,final:null,reasons:[],checked:'수집만 완료'},
{id:'DEMO-AI-005',title:'[합성] AI 상담서비스 24시간 운영 사업',org:'가상 고객서비스공단',cat:'AI',budget:'1.5억',end:'10.26',fit:69,margin:17,hard:'pass',ops:true,exp:true,score:63,rec:'no_bid',final:'no_bid',reasons:['24시간 운영 중심 사업','운영 부담 수용 기준 초과'],checked:'10.10 09:22'},
{id:'DEMO-DA-006',title:'[합성] 대용량 분석 데이터 통합 플랫폼',org:'가상 데이터원',cat:'DATA',budget:'8.0억',end:'11.02',fit:74,margin:null,hard:'unknown',ops:false,exp:false,score:67,rec:'hold',final:null,reasons:['제안요청서 검토 필요','사업 예상원가 미확인'],checked:'10.10 09:25'},
{id:'DEMO-SW-007',title:'[합성] 업무 데이터 API 및 대시보드',org:'가상 행정정보센터',cat:'SW',budget:'1.2억',end:'11.14',fit:89,margin:25,hard:'pass',ops:false,exp:true,score:89,rec:null,final:null,reasons:[],checked:'수집만 완료'},
{id:'DEMO-DA-008',title:'[합성] 공공 빅데이터 시각화 용역',org:'가상 지역혁신원',cat:'DATA',budget:'9,500만',end:'11.21',fit:79,margin:19,hard:'pass',ops:false,exp:false,score:72,rec:null,final:null,reasons:[],checked:'수집만 완료'}];
let notices=seed.map(x=>({...x,reasons:[...x.reasons]})),selected='DEMO-AI-001',filter='all',query='',sector='',page='notices',toasts=0,policyVersion=1,weightVersion=1;
const policyDefault={name:'AI·데이터 사업 기본 참여 기준',minFit:65,minMargin:15,require:true,ops:true,proof:true};
let policy={...policyDefault};
const gates=[
['eligibility','업종·기업규모 자격','공고문 / 나라장터 등록증'],
['licenses','면허·인증','공고문 / 증빙 유효기간'],
['track_record','필수 수행실적','제안요청서 / 실적증명'],
['resources','인력·재무 여건','사업관리 / 가용인력'],
['teaming','공동수급·지역 제한','정정공고 / 계약방식'],
['deadline','접수 기한·제출서류','공고 / 체크리스트'],
['security','보안·데이터 제약','제안요청서 / 수행환경'],
['contract','계약 배제 요건','특수조건 / 법무 검토']];
const factors=[
['technical','기술·솔루션 적합성',15],['staff','수행 인력·일정',10],['experience','유사 사업 실적',10],
['buyer','고객 요구 이해',10],['competition','경쟁사 대비 위치',10],['differentiation','차별성·가격 경쟁력',10],
['profit','사업 수익성·현금흐름',10],['bid_cost','제안비용·기회비용',5],
['relationship','고객 이해·과거 평가',5],['strategy','사업 전략 적합성',5],
['readiness','제안 준비도',5],['risk','계약·수행 위험 통제',5]];
let weights=Object.fromEntries(factors.map(v=>[v[0],v[2]]));
let logs=[
{stamp:'2026.10.10 09:20',id:'DEMO-AI-003',title:'[합성] 의료 AI 영상 판독 모델 개발',status:'no_bid',actor:'담당자 최종결정 (가상)',reason:'기술 적합성 기준 미달 / 의료영상 모델 개발 역량 부족',version:'판단 v1 · 영향인자 v1'},
{stamp:'2026.10.10 09:22',id:'DEMO-AI-005',title:'[합성] AI 상담서비스 24시간 운영 사업',status:'no_bid',actor:'담당자 최종결정 (가상)',reason:'24시간 운영 중심 사업 / 운영 부담 수용 기준 초과',version:'판단 v1 · 영향인자 v1'}
];
const names={bid:'참여 검토',no_bid:'불참 검토',hold:'확인 보류',pending:'판단 대기'};
let fullDetailTab='overview';
let toastTimer;
let profileConnection=null;

/* 로컬 127.0.0.1 앱에서만 프로필 JSON 영속화. 파일로 여는 시안은 기존 메모리 모드 유지. */
function applyStoredProfiles(state){
 if(!state||!Number.isInteger(state.revision)||!Number.isInteger(state.policy_version)||!Number.isInteger(state.factor_version)
   ||!state.policy||!state.weights||Object.keys(state.weights).length!==factors.length)throw Error('프로필 응답 계약 오류');
 policy={...state.policy};weights={...state.weights};
 policyVersion=state.policy_version;weightVersion=state.factor_version;
 renderPolicy();renderVariables();renderNotices();
 if(page==='full-detail')renderFullDetail();
}
async function loadStoredProfiles(){
 if(location.protocol!=='http:'||location.hostname!=='127.0.0.1'||location.pathname!=='/decision-preview')return;
 try{
  const response=await fetch('/api/decision-profiles',{headers:{Accept:'application/json'},cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const body=await response.json();
  if(body.storage!=='LOCAL_JSON'||typeof body.csrf!=='string')throw Error('로컬 저장 계약 오류');
  applyStoredProfiles(body.profiles);
  profileConnection={revision:body.profiles.revision,csrf:body.csrf};
  byId('storageMode').textContent='두 프로필은 이 PC의 decision_profiles.json에 저장합니다. 가상 판단과 불참 이력은 화면 임시 상태입니다.';
 }catch(error){
  profileConnection=null;
  notify('로컬 프로필 저장 연결을 확인하지 못했습니다. 변경 사항은 화면 임시 상태입니다.');
 }
}
async function commitProfile(kind,value){
 if(!profileConnection){
  if(kind==='policy'){policy=value;policyVersion++;renderPolicy();}
  else{weights=value;weightVersion++;renderVariables();}
  notify('화면 임시 프로필을 변경했습니다. 파일로 연 시안은 새로고침 시 초기화됩니다.');
  return;
 }
 const payload={expected_revision:profileConnection.revision,kind};
 if(kind==='policy')payload.profile=value;
 else payload.weights=value;
 try{
  const response=await fetch('/api/decision-profiles/save',{
   method:'POST',credentials:'same-origin',
   headers:{'Content-Type':'application/json','X-Local-CSRF':profileConnection.csrf},
   body:JSON.stringify(payload)
  });
  if(!response.ok){
   if(response.status===409){await loadStoredProfiles();throw Error('다른 창의 저장이 우선 적용됐습니다. 변경 내용을 확인하고 다시 저장하세요.');}
   throw Error('프로필 저장 실패: HTTP '+response.status);
  }
  const body=await response.json();
  if(!body.ok||body.storage!=='LOCAL_JSON')throw Error('서버 저장 응답 오류');
  applyStoredProfiles(body.profiles);
  profileConnection.revision=body.profiles.revision;
  notify(kind==='policy'?'참여 판단 기준을 로컬 JSON에 버전 저장했습니다.':'영향인자 가중치를 로컬 JSON에 버전 저장했습니다.');
 }catch(error){notify(error.message||'프로필 저장 오류. 기존 서버 값은 변경하지 않았습니다.');}
}
function notify(s){const t=byId('toast');t.textContent=s;t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),4500);}
function badge(key){return el('span','pill '+(key||'pending'),names[key]||names.pending);}
function getNotice(){return notices.find(n=>n.id===selected);}
function show(view){page=view;document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id==='view-'+view));document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));const titles={notices:'공고 목록',collection:'수집 관리',policy:'참여 판단 프로필',variables:'영향인자 프로필',history:'참여·불참 이력','full-detail':'공고 상세'};byId('breadcrumb').textContent=titles[view];if(view==='history')renderHistory();if(view==='full-detail')renderFullDetail();}
function summary(){const out={total:notices.length,pending:0,bid:0,hold:0,no_bid:0};notices.forEach(n=>{out[n.rec||'pending']++});return out;}
function renderKPIs(){const totals=summary();const defs=[['수집한 공고',totals.total,'합성 공고 목록','highlight'],['판단 대기',totals.pending,'평가 실행 전',''],['참여 검토',totals.bid,'최종 참여 결정 아님',''],['확인 보류',totals.hold,'근거·자료 확인 필요',''],['불참 검토',totals.no_bid,'사유 확인 가능','']];byId('kpis').replaceChildren();defs.forEach(a=>{const c=el('article','card kpi '+a[3]);c.append(el('div','klabel',a[0]),el('strong','kvalue',a[1]+'건'),el('div','ksub',a[2]));byId('kpis').append(c);});}
function renderFilters(){const entries=[['all','전체'],['pending','판단 대기'],['bid','참여 검토'],['hold','확인 보류'],['no_bid','불참 검토']];const container=byId('statusFilters');container.replaceChildren();entries.forEach(([key,label])=>{const b=el('button','filter'+(filter===key?' active':''),label);b.type='button';b.addEventListener('click',()=>{filter=key;renderNotices();});container.append(b);});}
function renderNotices(){renderKPIs();renderFilters();const list=notices.filter(n=>(filter==='all'||(n.rec||'pending')===filter)&&(!sector||n.cat===sector)&&(!query||[n.title,n.org,n.id].join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase())));byId('result-count').textContent=list.length+' / '+notices.length+'건';
 const container=byId('noticeRows');container.replaceChildren();byId('listEmpty').hidden=list.length!==0;
 list.forEach(n=>{const tr=el('tr',n.id===selected?'selected':'');const t=el('td');t.append(el('div','p-title',n.title),el('div','idline',n.org+' · '+n.id));if(n.rec==='no_bid')t.append(el('div','subline','불참 사유: '+n.reasons[0]));tr.append(t);tr.append(el('td','',n.cat==='DATA'?'데이터':n.cat),el('td','',n.budget),el('td','',n.end));
 const cell=el('td');cell.append(badge(n.rec||'pending'));tr.append(cell);const act=el('td');const b=el('button','btn small','상세보기');b.type='button';b.addEventListener('click',()=>openFullDetail(n.id));act.append(b);tr.append(act);
 tr.addEventListener('click',e=>{if(e.target.closest('button'))return;selected=n.id;renderNotices();});tr.style.cursor='pointer';container.append(tr);});
 renderDetail();
}
function logDecision(n,actor){logs.unshift({stamp:'2026.10.10 · 화면 시연',id:n.id,title:n.title,status:n.final||n.rec||'hold',actor:actor,reason:n.finalReason||(n.reasons.join(' / ')||'별도 사유 미입력'),version:'판단 v'+policyVersion+' · 영향인자 v'+weightVersion});}
function factorScore(n,key){
 const scaled=Math.max(1,Math.min(5,Math.round(n.fit/20)));
 if(key==='technical')return scaled;
 if(key==='staff')return n.ops?3:scaled;
 if(key==='experience')return n.exp?4:2;
 if(key==='profit')return n.margin===null?null:Math.max(1,Math.min(5,Math.round((n.margin+5)/7)));
 if(key==='bid_cost')return n.margin===null?null:n.margin>=20?4:2;
 if(key==='risk')return n.ops?1:4;
 if(key==='readiness')return n.hard==='unknown'?2:4;
 return Math.max(1,Math.min(5,Math.round((scaled+3)/2)));
}
function weightedFit(n){
 let total=0,count=0;
 factors.forEach(([key])=>{const score=factorScore(n,key);if(score===null)return;total+=score*weights[key];count+=weights[key];});
 return count?Math.round(total/count*20):null;
}
function assess(n){let rec='bid';let reasons=[];
 const weighted=weightedFit(n);
 if(n.hard==='fail'){rec='no_bid';reasons.push('공고의 필수 참가자격 미충족 (가상)');}
 else if(policy.require&&n.hard==='unknown'){rec='hold';reasons.push('필수 자격 증빙 확인 전');}
 else if(policy.proof&&!n.exp){rec='hold';reasons.push('실적증빙 자료 부족');}
 else if(policy.ops&&n.ops){rec='no_bid';reasons.push('운영·상주 중심 사업 제외 기준 적용');}
 else if(weighted!==null&&weighted<policy.minFit){rec='no_bid';reasons.push('가중 종합 적합도 '+weighted+'점 · 기준 '+policy.minFit+'점 미달');}
 else if(n.margin===null){rec='hold';reasons.push('원가·예상 이익률 확인 필요');}
 else if(n.margin<policy.minMargin){rec='no_bid';reasons.push('예상 이익률 '+n.margin+'% · 기준 '+policy.minMargin+'% 미달');}
 else{reasons.push('현재 가상 조건과 영향인자 프로필에서 참여 검토 가능');reasons.push('원문 증빙·실제 회사 기준 확인 필요');}
 n.rec=rec;n.reasons=reasons;n.checked='화면 시연 · 방금';n.policyRef='참여 판단 v'+policyVersion+' · 영향인자 v'+weightVersion;n.score=weighted;
 logDecision(n,'시뮬레이션 판별');}
function renderDetail(){const n=getNotice(),panel=byId('detail');panel.replaceChildren();if(!n){panel.append(el('p','muted','목록에서 공고를 선택하세요.'));return;}
 panel.append(el('div','detailTitle',n.title));const meta=el('div','detailMeta');[n.cat==='DATA'?'데이터분석':n.cat,n.org,n.id].forEach(t=>meta.append(el('span','',t)));panel.append(meta);
 const dl=el('dl','dl');[['사업 예산',n.budget],['접수 마감 (가상)',n.end],['판별 이력',n.checked],['담당자 최종결정',n.final==='no_bid'?'불참 (가상)':n.final==='bid'?'참여 (가상)':'미결정']].forEach(a=>{dl.append(el('dt','',a[0]),el('dd','',a[1]))});panel.append(dl,el('hr','hr'),el('h3','','참여 판단 결과'));panel.append(badge(n.rec||'pending'));
 const reason=el('div','callout');reason.style.marginTop='13px';reason.append(el('strong','','판단 사유 및 영향 요인'));
 if(n.reasons.length){const ul=el('ul','reasonList');n.reasons.forEach(v=>ul.append(el('li','',v)));reason.append(ul);}else reason.append(el('p','muted','아직 판단하지 않았습니다. 버튼을 누르면 가상 프로필 기준으로 근거가 표시됩니다.'));panel.append(reason);
 panel.append(el('h3','', '판단에 사용된 프로필'));const ps=el('p','muted',n.policyRef||'기본 참여 판단 v1 · 영향인자 v1 (초기 예시)');ps.style.marginBottom='13px';panel.append(ps);
 [['기술 적합성',n.fit+' / 100'],['영향인자 가중 종합',weightedFit(n)+' / 100 (가상 값)'],['예상 이익률',n.margin===null?'미확인':n.margin+'%'],['필수 참가조건',n.hard==='unknown'?'미확인':n.hard==='fail'?'불충족':'충족 가정'],['실적증빙',n.exp?'보유 가정':'미확인'],['운영 중심 여부',n.ops?'운영 중심':'구축·개발 중심']].forEach(v=>{const row=el('div','dl');row.style.marginBottom='8px';row.append(el('dt','',v[0]),el('dd','',v[1]));panel.append(row)});
 const actions=el('div','actions');actions.style.marginTop='20px';
 const judge=el('button','btn primary','참여 판단 시연');judge.addEventListener('click',()=>{assess(n);renderNotices();notify('저장된 참여판단 프로필 기준으로 화면 판단을 시연했습니다. 실제 AI 호출은 없습니다.');});
 const reasonInput=el('textarea');reasonInput.rows=2;reasonInput.placeholder='담당자가 확인한 최종 불참 사유를 입력하세요 (가상 예시만)';reasonInput.style.width='100%';reasonInput.style.marginTop='12px';reasonInput.setAttribute('aria-label','담당자 최종 불참 사유');reasonInput.value=n.finalReason||'';
 const decision=el('button','btn','담당자 최종 불참 기록');decision.addEventListener('click',()=>{if(!n.rec){notify('먼저 참여 판단을 실행하세요.');return;}const reason=reasonInput.value.trim();if(!reason){notify('불참 최종결정에는 담당자 사유를 입력해야 합니다.');reasonInput.focus();return;}n.final='no_bid';n.finalReason=reason;logDecision(n,'담당자 불참 기록 (화면 시연)');renderNotices();notify('담당자 불참 사유를 화면에 임시 기록했습니다. 실제 입찰 상태와 무관합니다.');});
 panel.append(reasonInput);const full=el('button','btn','전체 상세보기');full.addEventListener('click',()=>openFullDetail(n.id));actions.append(full,judge,decision);panel.append(actions);const note=el('p','muted','불참·보류 근거와 프로필 버전은 화면 시연 기록에만 남습니다. 새로고침하면 모두 초기화됩니다.');note.style.marginTop='13px';panel.append(note);
}
function renderPolicy(){byId('policyName').value=policy.name;byId('policyFit').value=policy.minFit;byId('policyMargin').value=policy.minMargin;byId('policyRequire').checked=policy.require;byId('policyOperations').checked=policy.ops;byId('policyProof').checked=policy.proof;byId('policyVersion').textContent='참여 판단 기준 v'+policyVersion+' · 가상 프로필';}
function savePolicy(){
 const minFit=Number(byId('policyFit').value),minMargin=Number(byId('policyMargin').value),name=byId('policyName').value.trim();
 if(!name||!Number.isFinite(minFit)||minFit<0||minFit>100||!Number.isFinite(minMargin)||minMargin< -100||minMargin>100){
  notify('이름·기술점수(0~100)·예상 이익률(-100~100)을 확인하세요.');return;
 }
 void commitProfile('policy',{name,minFit,minMargin,require:byId('policyRequire').checked,ops:byId('policyOperations').checked,proof:byId('policyProof').checked});
}
function renderVariables(){byId('gateVariables').replaceChildren();gates.forEach((g,i)=>{const c=el('div','callout');c.append(el('strong','',(i+1)+'. '+g[1]),el('p','muted','필요 근거: '+g[2]));byId('gateVariables').append(c);});const list=byId('factorWeights');list.replaceChildren();factors.forEach((f,i)=>{const row=el('div','weightRow');row.append(el('strong','',(i+1)+'. '+f[1]));const inp=el('input');inp.type='range';inp.min='0';inp.max='25';inp.step='1';inp.value=weights[f[0]];inp.dataset.weight=f[0];inp.setAttribute('aria-label',f[1]+' 가중치');const out=el('output','',inp.value+'%');inp.addEventListener('input',()=>{out.textContent=inp.value+'%';calcWeightTotal();});row.append(inp,out);list.append(row);});calcWeightTotal();}
function calcWeightTotal(){let total=0;document.querySelectorAll('[data-weight]').forEach(n=>{total+=Number(n.value)});byId('weightTotal').textContent='합계 '+total+'%';byId('saveFactors').disabled=total!==100;byId('weightTotal').className='pill '+(total===100?'bid':'no_bid');}

/* 전체 공고 상세 퍼블리싱: 기존 목록의 합성 상태와 프로필을 재사용한다. */
function openFullDetail(id,tab='overview'){
 if(!notices.some(n=>n.id===id)){notify('해당 공고가 목록에 없습니다.');return;}
 selected=id;fullDetailTab=tab;show('full-detail');window.scrollTo(0,0);
}
function detailText(tag,text,cls=''){return el(tag,cls,text);}
function detailBlock(title){const block=el('section','detailBlock');block.append(el('h3','',title));return block;}
function detailKV(items){
 const dl=el('dl','detailGrid');
 items.forEach(([key,value])=>{dl.append(el('dt','',key),el('dd','',String(value)));});return dl;
}
function renderFullDetail(){
 const n=getNotice(),hero=byId('fullDetailHero'),pane=byId('fullDetailPane'),tabs=byId('fullDetailTabs');
 hero.replaceChildren();pane.replaceChildren();
 if(!n){pane.append(el('p','muted','공고를 찾지 못했습니다. 목록에서 다시 선택하세요.'));return;}
 byId('fullDetailTitle').textContent=n.title;
 const headline=el('div','actions');headline.append(badge(n.rec||'pending'));headline.append(el('span','pill','가상 자료 · 공식 공고 확인 전'));hero.append(headline);
 hero.append(el('h2','','발주기관 '+n.org));const chips=el('div','heroMeta');
 [['가상 공고번호',n.id],['분야',n.cat==='DATA'?'데이터분석':n.cat],['예산 예시',n.budget],['마감 예시',n.end]].forEach(pair=>chips.append(el('span','',pair[0]+' · '+pair[1])));
 hero.append(chips);
 tabs.querySelectorAll('[data-detail-tab]').forEach(button=>{
  const active=button.dataset.detailTab===fullDetailTab;
  button.classList.toggle('active',active);button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;
 });
 const notice=el('div','detailNotice','이 페이지의 공고명·예산·마감·점수·요건은 모두 시연용 합성값입니다. 원문 링크와 첨부파일은 제공되지 않았으며 미확인 조건을 적격으로 판정하지 않습니다.');
 pane.append(notice);
 if(fullDetailTab==='overview')renderFullOverview(n,pane);
 else if(fullDetailTab==='requirements')renderFullRequirements(n,pane);
 else if(fullDetailTab==='evaluation')renderFullEvaluation(n,pane);
 else renderFullDecision(n,pane);
}
function demoScopes(n){
 if(n.ops)return ['24시간 서비스 운영 및 장애 대응 (가상)','서비스 수준 협약(SLA) 및 상주·교대 요구 확인 필요','운영인력 투입 가능성과 회사 수용 조건 검토'];
 if(n.cat==='DATA')return ['공공 데이터 수집·정제·품질검증 (가상)','Python/SQL 기반 데이터 처리와 분석 결과 제공 (가상)','데이터 보안·원천 API·납품 검사 기준 확인 필요'];
 if(n.cat==='AI')return ['업무용 AI 모델 또는 서비스 연동·검증 (가상)','AI 모델 결과 검증·사용자 서비스·API 연계 (가상)','모델 성능 평가·개인정보·라이선스 조건 확인 필요'];
 return ['업무 웹서비스·API 구축 (가상)','기존 시스템·DB 연계 및 사용자 UI 구현 (가상)','운영·배포·보안 의무사항 확인 필요'];
}
function renderFullOverview(n,pane){
 const columns=el('div','detailColumns'),info=detailBlock('사업 기본정보'),source=detailBlock('원문·첨부파일 상태');
 info.append(detailKV([['사업명',n.title],['발주기관',n.org],['공고 식별자',n.id+' (가상)'],
  ['대상 분야',n.cat==='DATA'?'데이터분석':n.cat],['예산',n.budget+' (가상)'],
  ['입찰 마감',n.end+' (가상)'],['사업 기간','공식 RFP 미확인'],
  ['계약 방식','공식 공고 미확인'],['참여 제한','공식 공고 미확인'],
  ['공고 차수/정정 상태','공식 원문 미연결'],['최신 확인 시점','미확인']]));
 source.append(el('p','desc','정식 연동 시 공고번호·정정차수별 원문과 첨부를 다운로드/조회할 영역입니다.'));
 const files=[['입찰공고문','원문 미수집'],['제안요청서(RFP)','첨부 미수집'],['과업지시서','첨부 존재 여부 미확인'],['평가표 및 계약특수조건','첨부 존재 여부 미확인']];
 files.forEach(([name,status])=>{const row=el('div','requirementRow');row.append(el('strong','',name),el('span','pill pending','미확인'),el('span','evidence',status));source.append(row);});
 source.append(el('p','helper','첨부 표시에는 실제 파일 다운로드 기능이 없으며, 임의 문서·외부 URL을 생성하지 않습니다.'));
 columns.append(info,source);pane.append(columns);
 const task=detailBlock('과업 범위 미리보기 (업무 유형별 가상 예시)');
 const ul=el('ul','reasonList');demoScopes(n).forEach(line=>ul.append(el('li','',line)));task.append(ul);task.style.marginTop='15px';pane.append(task);
}
function gateFor(n,key){
 if(key==='eligibility')return n.hard==='fail'?['미충족 가정','가상 업종·참가자격 미충족 입력 (공식 서류 미확인)']:
  n.hard==='pass'?['충족 가정','화면 합성데이터에 충족 가정이 있으나 확인된 법적 증빙 없음']:
  ['미확인','입찰업종·등록 자격증빙 미제공'];
 if(key==='track_record')return n.exp?['충족 가정','가상의 실적 보유 입력; 실적증명 원문 미확인']:['미확인','필수 수행실적 증빙 자료 없음'];
 if(key==='resources')return n.ops?['추가 검토','24시간 운영 인력·가용성 미확인']:['미확인','실제 인력 배치와 수익성·재무조건 미확인'];
 return ['미확인','원문 요구조건·회사 증빙 대조 전'];
}
function renderFullRequirements(n,pane){
 const split=el('div','detailColumns'),left=detailBlock('요구사항 및 과업 범위'),right=detailBlock('자격 심사 전 확인 사항');
 const ul=el('ul','reasonList');demoScopes(n).forEach(x=>ul.append(el('li','',x)));left.append(ul);
 left.append(el('p','helper','실제 제안요청서의 요구사항 ID·페이지·표준/기술·수행기간은 연동 후 확인합니다.'));
 const list=el('ul','reasonList');[
 '최신 공고 차수 및 입찰참가 등록 업종','필수 실적의 인정 조건과 증빙 유효기간',
 '투입인력 자격·가용 일정, 공동수급 가능 여부','사업 범위 및 보안·수행 장소 제한',
 '접수·제안서 제출 일정과 계약특수조건'
 ].forEach(x=>list.append(el('li','',x)));right.append(list);split.append(left,right);pane.append(split);
 const section=detailBlock('필수 참가조건 8개 · 미검증 판단 초안');section.style.marginTop='16px';
 gates.forEach(([key,name,evidence])=>{
  const [status,why]=gateFor(n,key),r=el('article','requirementRow');
  const title=el('div');title.append(el('strong','',name),el('small','','필요 근거: '+evidence));
  r.append(title,el('span','pill '+(status.includes('미충족')?'no_bid':'hold'),status),el('span','evidence',why));
  section.append(r);
 });pane.append(section);
}
function renderFullEvaluation(n,pane){
 const split=el('div','detailColumns'),left=detailBlock('판단 당시 영향인자와 사업성'),right=detailBlock('적용 프로필 및 점수 해석');
 const current=weightedFit(n);
 left.append(detailKV([['기술 적합성 (화면 입력)',n.fit+' / 100 (합성)'],
  ['마지막 판단의 가중 종합값',n.rec?(n.score===null?'미확인':String(n.score??'기존 예시 점수')+' / 100'):'판단 전'],
  ['현재 가중치로 계산한 예시',current===null?'미확인':current+' / 100'],
  ['예상 사업이익률',n.margin===null?'미확인':n.margin+'% (합성 원가)'],
  ['실제 원가/수주율','미검증']]));
 right.append(detailKV([['참여 판단 기준',n.policyRef||'초기 시연 기준 (실제 판단 이력 미검증)'],
  ['현재 정책 프로필',policy.name+' · v'+policyVersion],
  ['현재 영향인자 버전','v'+weightVersion],['점수 기준','1점 불리 · 5점 유리'],['평가 전제','가상의 사업역량 값']]));
 if(n.rec && n.policyRef && n.policyRef!==('참여 판단 v'+policyVersion+' · 영향인자 v'+weightVersion)){
  right.append(el('div','detailNotice','프로필이 이후 변경되었습니다. 과거 판단은 유지하며, 새 기준을 적용하려면 재판단 버튼을 눌러야 합니다.'));
 }
 split.append(left,right);pane.append(split);
 const section=detailBlock('평가요인 12개와 근거 (합성 산출)');section.style.marginTop='16px';
 factors.forEach(([key,label])=>{
  const score=factorScore(n,key),pct=weights[key],row=el('div','variableRow');
  const first=el('div');first.append(el('strong','',label));const bar=el('div','metricBar'),part=el('i');part.style.width=(score===null?0:score*20)+'%';bar.append(part);first.append(bar);
  row.append(first,el('span','score',score===null?'미확인':score+' / 5'),el('span','muted','가중치 '+pct+'%'),
   el('span','evidence',score===null?'근거 데이터 부족 (예시 점수 없음)':'합성 부서/공고 특징 기반 표시, 원문 근거 미연결'));
  section.append(row);
 });pane.append(section);
}
function renderFullDecision(n,pane){
 const split=el('div','detailColumns'),left=detailBlock('참여 판단 결과 및 불참 사유'),right=detailBlock('담당자 최종 결정');
 const result=el('div','actions');result.append(badge(n.rec||'pending'));left.append(result);
 if(n.reasons.length){const ul=el('ul','reasonList');n.reasons.forEach(x=>ul.append(el('li','',x)));left.append(ul);}
 else left.append(el('p','muted','아직 참여 판단을 실행하지 않았습니다. 위쪽 버튼으로 시연할 수 있습니다.'));
 left.append(el('p','helper','가상 판단은 참여 판단 프로필과 12개 영향인자 가중치로 계산하며 실제 AI 분석 결과가 아닙니다.'));
 left.append(detailKV([['판단 시각',n.checked],['판단에 사용된 프로필',n.policyRef||'가상 초기 예시 (버전 미검증)']]));
 right.append(detailKV([['최종 참여결정',n.final==='no_bid'?'불참 (합성 시연)':n.final==='bid'?'참여 (합성 시연)':'미결정'],
  ['담당자 불참 이유',n.finalReason||(n.final==='no_bid'?n.reasons.join(' / '):'아직 없음')]]));
 const label=el('label','','담당자 최종 불참 사유 (필수)');
 const note=el('textarea','detailTextarea');note.id='fullDetailNoBidReason';note.maxLength=500;
 note.placeholder='판단 근거를 검토한 뒤 직접 불참 사유를 적으세요 (가상의 예시만)';
 note.value=n.finalReason||'';label.append(note);right.append(label);
 const save=el('button','btn primary','담당자 최종 불참 기록 시연');save.type='button';save.style.marginTop='12px';
 save.addEventListener('click',()=>recordHumanNoBid(n,note.value));right.append(save);
 split.append(left,right);pane.append(split);
 const hist=detailBlock('이 공고의 판단·결정 이력');hist.style.marginTop='16px';
 const entries=logs.filter(x=>x.id===n.id);
 if(entries.length===0)hist.append(el('p','muted','판단 이력이 없습니다. 참여 판단 버튼을 누르면 화면 임시 이력이 생성됩니다.'));
 else {const timeline=el('div','timeline');
  entries.forEach(x=>{const item=el('article');item.append(el('strong','',x.stamp+' · '+x.actor));
   item.append(el('p','',x.reason),el('p','muted',x.version));timeline.append(item);});
  hist.append(timeline);
 }pane.append(hist);
}
function recordHumanNoBid(n,text){
 if(!n.rec){notify('먼저 참여 판단을 실행하세요.');return;}
 const reason=text.trim();
 if(!reason){notify('담당자 불참 사유를 입력해 주세요.');const input=byId('fullDetailNoBidReason');if(input)input.focus();return;}
 n.final='no_bid';n.finalReason=reason;logDecision(n,'담당자 최종 불참 기록 (화면 시연)');
 renderNotices();if(page==='full-detail')renderFullDetail();notify('담당자 불참 사유를 화면 임시 이력에 기록했습니다. 실제 입찰 제출/결정이 아닙니다.');
}

function renderHistory(){const selectedFilter=byId('historyFilter').value;const rows=byId('historyRows');rows.replaceChildren();const visible=logs.filter(x=>!selectedFilter||x.status===selectedFilter);if(!visible.length){rows.append(el('div','empty','이 상태의 판단 이력이 없습니다.'));return;}visible.forEach(v=>{const row=el('article','historyRow');row.append(el('div','muted',v.stamp));const main=el('div');main.append(el('h3','',v.title),el('p','',v.actor+' · '+v.reason),el('p','muted',v.version));row.append(main);const status=el('div');status.append(badge(v.status));const detailButton=el('button','btn small','공고 근거 보기');detailButton.style.display='block';detailButton.style.marginTop='8px';detailButton.addEventListener('click',()=>{filter='all';query='';sector='';byId('search').value='';byId('sector').value='';openFullDetail(v.id,'decision')});status.append(detailButton);row.append(status);rows.append(row);});}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{show(b.dataset.view);if(b.dataset.view==='variables')renderVariables();if(b.dataset.view==='policy')renderPolicy();}));
byId('detailBack').addEventListener('click',()=>{show('notices');renderNotices();});
byId('detailAssess').addEventListener('click',()=>{const n=getNotice();if(!n)return;assess(n);renderNotices();renderFullDetail();notify('이 공고의 가상 참여 판단을 갱신했습니다. 실제 AI 호출은 없습니다.');});
byId('fullDetailTabs').querySelectorAll('[data-detail-tab]').forEach(b=>b.addEventListener('click',()=>{fullDetailTab=b.dataset.detailTab;renderFullDetail();}));
byId('fullDetailTabs').addEventListener('keydown',event=>{
 if(event.key!=='ArrowLeft'&&event.key!=='ArrowRight')return;
 const buttons=[...byId('fullDetailTabs').querySelectorAll('[data-detail-tab]')];
 const idx=buttons.findIndex(b=>b.dataset.detailTab===fullDetailTab);
 const dir=event.key==='ArrowRight'?1:-1;
 const next=buttons[(idx+dir+buttons.length)%buttons.length];
 fullDetailTab=next.dataset.detailTab;renderFullDetail();next.focus();event.preventDefault();
});
byId('jump-collection').addEventListener('click',()=>show('collection'));byId('goto-notices').addEventListener('click',()=>show('notices'));
byId('search').addEventListener('input',e=>{query=e.target.value.trim();renderNotices();});byId('sector').addEventListener('change',e=>{sector=e.target.value;renderNotices();});
byId('historyFilter').addEventListener('change',renderHistory);
byId('assess-all').addEventListener('click',()=>{let count=0;notices.forEach(n=>{if(!n.rec){assess(n);count++}});renderNotices();notify(count+'개 합성 공고의 판별을 시연했습니다. 실제 Codex 호출 및 입찰 결정은 없습니다.');});
function simulateCollect(){if(notices.some(n=>n.id==='DEMO-NEW-009')){notify('이미 가상 공고를 1건 추가했습니다. 새로고침 시 초기화됩니다.');return;}notices.unshift({id:'DEMO-NEW-009',title:'[합성] 지자체 AI 데이터 검색·분석 플랫폼',org:'가상 스마트행정센터',cat:'DATA',budget:'2.7억',end:'11.19',fit:87,margin:22,hard:'unknown',ops:false,exp:true,score:79,rec:null,final:null,reasons:[],checked:'화면 수집 시연 · 방금'});selected='DEMO-NEW-009';show('notices');renderNotices();notify('가상 공고 1건을 화면 목록에 추가했습니다. 실제 수집은 수행하지 않았습니다.');}
byId('demo-collect').addEventListener('click',simulateCollect);byId('collect-action').addEventListener('click',simulateCollect);
byId('savePolicy').addEventListener('click',savePolicy);byId('resetPolicy').addEventListener('click',()=>{void commitProfile('policy',{...policyDefault});});
byId('saveFactors').addEventListener('click',()=>{const next={};document.querySelectorAll('[data-weight]').forEach(x=>next[x.dataset.weight]=Number(x.value));if(Object.values(next).reduce((a,b)=>a+b,0)!==100){notify('평가요인 가중치 합계가 100%여야 합니다.');return;}void commitProfile('factors',next);});
byId('resetFactors').addEventListener('click',()=>{void commitProfile('factors',Object.fromEntries(factors.map(v=>[v[0],v[2]])));});
renderNotices();renderPolicy();renderVariables();void loadStoredProfiles();
