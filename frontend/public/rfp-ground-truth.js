/**
 * BID-06 로컬 원본 정답 검수 설계 계약.
 * 책임: 기존 화면에 목록/원본 대조/독립 정답 편집/승인·보류/표본 지표를 제공한다.
 * 경계: 모든 비신뢰 문장은 textContent, 원본은 선택한 파일만 메모리 전송한다.
 * 부작용: 명시 저장 버튼만 CSRF POST, 자동 다운로드/저장/승인·외부 요청 없음.
 * 실패: 10초 취소·최신 조회 우선, 충돌 시 입력 보존/명시 재조회. 오류 원문 미표시.
 * 불변: 후보를 정답으로 자동 복사하지 않는다. SHA/내부 값은 details에만 표시한다.
 * 관련: BID06_GROUND_TRUTH_2026-10-19.md, test_rfp_ground_truth_ui.cjs.
 */
(function () {
  'use strict';
  const categoryLabels={participation:'참가자격',evaluation:'평가기준',scope:'과업 요구사항·범위'};
  const routeLabels={TEXT:'본문',TABLE:'표',FOOTNOTE:'각주',IMAGE:'이미지',OCR:'OCR'};
  const api='/api/dashboard/rfp-ground-truth';
  function node(tag,text='') {const n=document.createElement(tag);n.textContent=text;return n;}
  function button(text,action){const n=node('button',text);n.type='button';n.addEventListener('click',action);return n;}
  function field(parent,label,input){const wrap=node('label',label+' ');wrap.style.display='block';wrap.style.margin='8px 0';wrap.append(input);parent.append(wrap);return input;}
  function input(value,type='text'){const n=node('input');n.type=type;n.value=String(value);n.style.maxWidth='100%';return n;}
  function select(options,value){const s=node('select');Object.entries(options).forEach(([v,label])=>{const o=node('option',label);o.value=v;s.append(o);});s.value=value;return s;}
  function box(parent,label){return field(parent,label,input('','checkbox'));}
  function safePre(text){const p=node('pre',text);Object.assign(p.style,{whiteSpace:'pre-wrap',overflowWrap:'anywhere',maxHeight:'340px',overflow:'auto',fontSize:'14px'});return p;}
  function metricText(m){return ['tp','fp','fn','precision','recall','f1','miss_rate'].map(k=>k+': '+
    (m[k]===null?'미평가':k.length<=2?String(m[k]):(100*m[k]).toFixed(1)+'%')).join(' · ');}
  async function request(path,options={}){
    const control=new AbortController(),timer=setTimeout(()=>control.abort(),10000);
    try{
      const r=await fetch(path,{cache:'no-store',credentials:'same-origin',...options,signal:control.signal});
      if(!r.ok)throw Error(r.status===409?'CONFLICT':'REQUEST');
      return await r.json();
    }finally{clearTimeout(timer);}
  }
  function mount(host,ident=null){
    const panel=node('section');panel.className='card';panel.classList.add('bid06Review');
    panel.append(node('h2','RFP 독립 정답 검수 · 표본 평가'));
    const status=node('p','조회 전입니다. 승인 정답이 없으면 NOT_EVALUATED입니다.');status.setAttribute('role','status');
    const content=node('div');let generation=0,pending=false;
    const refresh=button(ident?'검수 자료 다시 조회':'RFP 정답 검수 대상 조회',()=>void load(ident));
    panel.append(status,refresh,content);host.append(panel);
    async function load(id){
      if(pending)return;
      const ticket=++generation;refresh.disabled=true;content.replaceChildren();status.textContent='기존 로컬 자료를 읽고 있습니다.';
      try{
        const data=await request(api+(id?'?id='+encodeURIComponent(id):''));
        if(ticket!==generation)return;
        if(id){if(!data.review||data.review.context.id!==id)throw Error('SCHEMA');render(data.review,data.csrf,id);}
        else{
          if(!Array.isArray(data.review_list)||!Number.isInteger(data.total)||data.storage!=='LOCAL_PRIVATE_REVIEW')throw Error('SCHEMA');
          status.textContent='검수 대상 '+data.total+'건 · 표시 '+data.review_list.length+'건 · 생략 '+data.omitted+'건. 분야 불일치로 제외하지 않습니다.';
          if(!data.total)content.append(node('p','검수 가능한 저장 문서가 없습니다. 공식 자료 확보 전 판단을 보류합니다.'));
          data.review_list.forEach(row=>{const item=node('article');item.style.margin='16px 0';
            item.append(node('strong',row.title),node('p',(row.lifecycle||'미확인')+' · '+(row.review_status||'최신성 미검증')),
              button('원본·정답 비교 검수',()=>void load(row.id)));content.append(item);});
        }
      }catch(_){if(ticket===generation){status.textContent='검수 조회 실패. 기존 자료는 보존되며 0건으로 판단하지 않습니다.';content.replaceChildren();}}
      finally{if(ticket===generation)refresh.disabled=false;}
    }
    function render(review,csrf,id){
      const ctx=review.context;content.replaceChildren();
      status.textContent='실자료는 사람의 원본 확인·독립 정답 승인 전 NOT_EVALUATED입니다. 적격·수익·인력/MM UNVERIFIED.';
      const overview=node('section');overview.append(node('h3','승인 표본 평가'),
        node('p',review.evaluation.state+' · 승인 정답 '+review.evaluation.approved_gold_count+'개 · 승인 범위 '+review.evaluation.approved_scope_count+'개'),
        node('p',metricText(review.evaluation.metrics)),node('p','평가 범위: 사람이 선택한 원본 페이지와 표시된 추출 후보만. 전체 문서 정확도·대표성 미확인. 생략 후보 '+ctx.omitted_candidate_count+'개.'),
        node('p','재검수 필요 표본 '+review.stale_scope_count+'개. 공식 최신성은 사람 확인 시점 기준이며 자동 보증하지 않습니다.'));
      Object.entries(review.evaluation.by_category).forEach(([c,m])=>overview.append(node('p',categoryLabels[c]+' · '+metricText(m))));
      const paths=node('details');paths.append(node('summary','표·각주·OCR 경로별 평가 펼치기'));
      Object.entries(review.evaluation.by_route).forEach(([r,m])=>paths.append(node('p',routeLabels[r]+' · '+metricText(m))));overview.append(paths);content.append(overview);
      if(!ctx.documents.length){content.append(node('p','원본·캐시 결속을 확인할 수 없습니다. 자료 보완 전 검수를 보류합니다.'));return;}
      const choose=field(content,'검수할 공식 첨부',select(Object.fromEntries(ctx.documents.map(d=>[d.identity,d.name])),ctx.documents[0].identity));
      const editor=node('div');content.append(editor);
      function edit(previous=null){
        if(pending)return;
        editor.replaceChildren();let sourceTicket='',originalText='',lastRequest=null,fileGeneration=0;
        const doc=ctx.documents.find(d=>d.identity===choose.value);if(!doc)return;
        const scopeId=previous?.scope_id||crypto.randomUUID();
        const metadata=node('details');metadata.append(node('summary','공식 출처·차수·SHA 상세'));
        metadata.append(node('p','공고 '+ctx.bid_no+' / 차수 '+ctx.bid_order+' / '+doc.binding),node('p','원본 SHA-256 '+doc.source_sha256));
        const link=node('a','공식 첨부 출처 열기');link.href=doc.official_url;link.target='_blank';link.rel='noopener noreferrer';metadata.append(link);editor.append(metadata);
        editor.append(node('p',ctx.blocked?'취소·구차수·정정/상태 미확인: 승인을 보류하고 이력만 보존합니다.':'공식 최신성·취소/정정 여부를 원본에서 사람이 확인해야 합니다.'),
          node('p','추출 상태: '+(doc.truncated?'잘림 있음':'저장 텍스트 범위만 확인')+' / '+(doc.parser_warnings_present?'파서 경고 있음':'표·각주·OCR는 별도 검수 필요')));
        const sourceStatus=node('p','선택한 로컬 원본의 SHA를 먼저 대조하세요. 원본 파일은 저장하지 않습니다.');sourceStatus.setAttribute('role','status');
        const file=field(editor,'PC의 공식 원본 선택',input('','file'));file.className='bid06OriginalFile';
        const original=safePre('원본은 PC의 문서 뷰어에서 전체 페이지·표·각주·이미지/OCR를 확인하세요. TXT 선택 시 여기에도 표시합니다.');
        const compare=button('선택 원본 SHA 대조',async()=>{
          const generation=++fileGeneration;
          compare.disabled=true;sourceTicket='';
          try{
            const f=file.files?.[0];if(!f||f.size<1||f.size>8*1024*1024)throw Error('FILE');
            const bytes=new Uint8Array(await f.arrayBuffer());let encoded='';
            for(let i=0;i<bytes.length;i+=8192)encoded+=String.fromCharCode(...bytes.subarray(i,i+8192));
            const result=await request(api+'/source-check',{method:'POST',headers:{'Content-Type':'application/json','X-Local-CSRF':csrf},
              body:JSON.stringify({id,identity:doc.identity,version_key:ctx.version_key,base64:btoa(encoded)})});
            if(result.ok!==true||result.source_sha_checked!==true||typeof result.source_ticket!=='string')throw Error('SCHEMA');
            if(generation!==fileGeneration)return;
            sourceTicket=result.source_ticket;sourceStatus.textContent='로컬 원본 SHA 일치. 공식 최신성·검수 범위는 별도 사람 확인 필요 (15분 안에 명시 저장).';
            if(/\.txt$/i.test(f.name)){originalText=await f.text();original.textContent=originalText;}
          }catch(_){if(generation===fileGeneration)sourceStatus.textContent='원본 대조 실패. 파일·차수·정정 상태를 확인한 후 다시 선택하세요.';}
          finally{compare.disabled=false;}
        });
        file.addEventListener('change',()=>{++fileGeneration;sourceTicket='';sourceStatus.textContent='파일이 바뀌었습니다. 원본 SHA를 다시 대조하세요.';original.textContent='선택한 원본을 PC 문서 뷰어에서 확인하세요.';});
        editor.append(compare,sourceStatus,node('h3','원본 확인'),original,node('h3','기존 추출 텍스트 (페이지 번호 아님)'),safePre(doc.text));
        const candidates=ctx.candidates.filter(c=>c.identity===doc.identity);editor.append(node('h3','비교할 기존 추출 후보'));
        candidates.forEach(c=>editor.append(node('p',categoryLabels[c.category]+' · 문자 '+c.start+'–'+c.end+' · '+c.text)));
        const range=node('fieldset');range.append(node('legend','사람이 확인한 표본 범위'));
        const s=previous?.scope||{start:0,end:doc.text.length,page_start:1,page_end:1,location:'',route:'TEXT'};
        const start=field(range,'추출 문자 시작',input(s.start,'number'));start.className='bid06Start';
        const end=field(range,'추출 문자 끝',input(s.end,'number'));end.className='bid06End';
        const pageStart=field(range,'원본 시작 페이지',input(s.page_start,'number'));pageStart.className='bid06PageStart';
        const pageEnd=field(range,'원본 끝 페이지',input(s.page_end,'number'));pageEnd.className='bid06PageEnd';
        const location=field(range,'원본 표·각주·문단 위치',input(s.location));location.maxLength=200;location.className='bid06Location';
        const route=field(range,'사람이 확인한 추출 경로',select(routeLabels,s.route));route.className='bid06Route';editor.append(range);
        editor.append(node('h3','원본에서 독립적으로 확인한 정답 구절'),node('p','추출 후보를 그대로 승인하지 마세요. 원본에서 확인한 세 유형의 정답을 등록하세요. 누락된 구절도 수동 입력합니다.'));
        const goldRows=node('div'),entries=[];editor.append(goldRows);
        function addGold(row={category:'participation',text:'',page:s.page_start,location:''}){
          const item=node('fieldset');item.className='bid06Gold';
          const category=field(item,'분류',select(categoryLabels,row.category));category.className='bid06GoldCategory';
          const text=field(item,'원본 정답 구절',node('textarea'));text.value=row.text;text.maxLength=1000;text.rows=4;text.style.width='100%';text.className='bid06GoldText';
          const page=field(item,'원본 페이지',input(row.page,'number'));page.className='bid06GoldPage';
          const position=field(item,'표/각주/문단 위치',input(row.location));position.maxLength=200;position.className='bid06GoldLocation';
          const entry={item,category,text,page,position,removed:false};entries.push(entry);
          item.append(button('이 정답 행 제거',()=>{entry.removed=true;item.remove();}));goldRows.append(item);
        }
        (previous?.gold||[]).forEach(addGold);
        editor.append(button('누락·정답 구절 수동 추가',()=>{if(entries.filter(e=>!e.removed).length<30)addGold();}));
        const checks=node('fieldset');checks.append(node('legend','선택한 원본 페이지 범위의 확인 상태'));
        const checkInputs={};
        Object.entries({pages:'전체 선택 페이지',tables:'표',footnotes:'각주',images:'이미지',ocr:'OCR 문자/이미지 원문 대조'}).forEach(([key,label])=>{
          checkInputs[key]=field(checks,label,select({UNKNOWN:'미확인',REVIEWED:'원본 대조 완료',NOT_APPLICABLE:'해당 없음'},'UNKNOWN'));
          checkInputs[key].className='bid06Check-'+key;
        });
        const latest=box(checks,'공식 출처에서 최신 차수·정정/취소 여부와 선택 원본의 일치를 직접 확인했습니다');latest.className='bid06Latest';
        const independent=box(checks,'원본에서 세 유형의 정답을 독립 확인했고 이 페이지/문자 범위 대응 및 누락을 검수했습니다');independent.className='bid06Independent';editor.append(checks);
        const feedback=node('p');feedback.setAttribute('role','status');feedback.className='bid06SaveStatus';editor.append(feedback);
        const approve=button('독립 정답 승인·평가 저장',()=>void save('APPROVED'));
        const hold=button('검수 보류 저장',()=>void save('HOLD'));
        approve.disabled=ctx.blocked||doc.binding!=='VERSION_MATCHED';editor.append(approve,hold);
        async function save(state){
          if(pending)return;
          if(state==='APPROVED'&&(!sourceTicket||!latest.checked||!independent.checked||checkInputs.pages.value!=='REVIEWED'
            ||Object.values(checkInputs).some(c=>c.value==='UNKNOWN'))){feedback.textContent='원본 SHA 대조·최신성·독립 정답·전체 검수 범위 확인이 필요합니다.';return;}
          pending=true;approve.disabled=true;hold.disabled=true;refresh.disabled=true;choose.disabled=true;
          try{
            const body={id,expected_revision:review.revision,scope_id:scopeId,
              version_key:ctx.version_key,identity:doc.identity,scope:{start:Number(start.value),end:Number(end.value),
                page_start:Number(pageStart.value),page_end:Number(pageEnd.value),location:location.value,route:route.value},
              gold:entries.filter(e=>!e.removed).map(e=>({category:e.category.value,text:e.text.value,page:Number(e.page.value),location:e.position.value})),
              status:state,checks:Object.fromEntries(Object.entries(checkInputs).map(([k,v])=>[k,v.value])),
              official_current_confirmed:latest.checked,independent_review_confirmed:independent.checked,source_ticket:sourceTicket};
            const fingerprint=JSON.stringify(body);
            if(!lastRequest||lastRequest.fingerprint!==fingerprint)lastRequest={fingerprint,request_id:crypto.randomUUID()};
            body.request_id=lastRequest.request_id;
            const data=await request(api+'/save',{method:'POST',headers:{'Content-Type':'application/json','X-Local-CSRF':csrf},body:JSON.stringify(body)});
            if(data.ok!==true||!data.review)throw Error('SCHEMA');
            pending=false;render(data.review,data.csrf,id);status.textContent='검수 기록 저장 완료. 기존 원본·추출·승인 이력은 보존됩니다.';
          }catch(e){feedback.textContent=e.message==='CONFLICT'?'공고·원본·다른 창의 검수 변경 또는 원본 대조 만료입니다. 입력을 보존했습니다. 재조회 후 확인하세요.':'검수 저장 실패. 입력과 기존 자료는 보존됩니다. 범위·중복·검수 확인 상태를 점검하세요.';}
          finally{pending=false;approve.disabled=ctx.blocked||doc.binding!=='VERSION_MATCHED';hold.disabled=false;refresh.disabled=false;choose.disabled=false;}
        }
      }
      choose.addEventListener('change',()=>edit());edit();
      const prior=node('section');prior.append(node('h3','저장 표본·변경 이력'));
      review.scopes.forEach(scope=>prior.append(node('p',scope.status+' · '+scope.validity+' · '+scope.recorded_at),
        button('이 표본 수정·재검수',()=>{choose.value=scope.identity;edit(scope);} )));
      const history=node('details');history.append(node('summary','승인·수정·보류 이력 펼치기'));
      review.history.forEach(h=>history.append(node('p',h.recorded_at+' · '+h.status)));prior.append(history);content.append(prior);
    }
    return {load};
  }
  window.rfpGroundTruth={mount,metricText};
})();
