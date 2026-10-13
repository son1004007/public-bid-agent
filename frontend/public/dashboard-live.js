/**
 * 로컬 공고 대시보드 실제 데이터 연결.
 * 목적: 기존 정적 퍼블리싱의 목록·상세·수집·판단·이력을 PC의 읽기/쓰기 API에 연결.
 * 보안: 127.0.0.1 /decision-preview에만 활성화; 공식 데이터의 검증 전 요건·점수는 표시 금지.
 * 상태: 공고·담당자 최종결정과 이력은 dashboard.json으로 원자 저장, 외부 AI 호출 없음.
 * 실패: 공식 API 오류를 합성 자료/0건으로 위장하지 않고 기존 자료를 유지한다.
 */
(function () {
  'use strict';
  if (location.protocol !== 'http:' || location.hostname !== '127.0.0.1'
      || location.pathname !== '/decision-preview') return;

  let connected = false;
  let revision = 0;
  let csrf = '';
  let departmentProfile = {revision:0,categories:['AI','SW','DATA','SECURITY'],include_review:false};

  // 기본은 마감 전·확인필요만 표시하되, 모든 API 원본을 DB에 그대로 남긴다.
  window.officialListFilter = function(n) {
    const deadline = byId('deadlineView').value;
    const windowStatus = n.window_status || 'UNKNOWN';
    const lifecycle = n.notice_lifecycle || 'CURRENT';
    if (deadline !== 'all' && (['CANCELLED','SUPERSEDED','REVIEW'].includes(lifecycle)
        || windowStatus === 'CANCELLED' || windowStatus === 'SUPERSEDED' || windowStatus === 'CLOSED')) return false;
    if (deadline === 'open' && windowStatus !== 'OPEN') return false;
    const selected = departmentProfile.categories || [];
    const matched = (n.department_categories || []).some(k => selected.includes(k));
    const state = n.department_status || 'REVIEW';
    const view = byId('departmentView').value;
    if (view === 'all') return true;
    if (view === 'candidate') return state === 'CANDIDATE' && matched;
    if (view === 'review') return state === 'REVIEW' || (state === 'CANDIDATE' && !matched);
    return (state === 'CANDIDATE' && matched) || (departmentProfile.include_review &&
      (state === 'REVIEW' || !n.department_status));
  };

  async function readDepartment() {
    const r = await fetch('/api/department-profile',{cache:'no-store',headers:{Accept:'application/json'}});
    if (!r.ok) throw Error('부서 분야 설정 조회 실패');
    const result = await r.json();
    departmentProfile = result.profile;
    byId('departmentProfileCard').hidden = false;
    byId('departmentChoices').querySelectorAll('input[type=checkbox]').forEach(input => {
      input.checked = departmentProfile.categories.includes(input.value);
    });
    byId('includeReview').checked = departmentProfile.include_review;
    byId('departmentProfileStatus').textContent = '부서 관심분야 설정 버전 '+
      departmentProfile.revision + ' · 법적 참여자격은 별도 확인이 필요합니다.';
    renderNotices();
  }

  async function saveDepartment() {
    const categories = [...byId('departmentChoices').querySelectorAll('input:checked')].map(x=>x.value);
    const payload = {expected_revision: departmentProfile.revision,profile:{
      categories,include_review:byId('includeReview').checked
    }};
    try {
      const r = await fetch('/api/department-profile/save',{
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-Local-CSRF':csrf},
        body:JSON.stringify(payload)
      });
      const response = await r.json();
      if (!r.ok || response.ok !== true) throw Error(response.error || '부서 분야 설정 저장 실패');
      departmentProfile = response.profile;
      byId('departmentProfileStatus').textContent = '부서 분야 설정을 PC에 저장했습니다. 버전 '+
        departmentProfile.revision;
      renderNotices();
    } catch(error) {
      byId('departmentProfileStatus').textContent = '부서 분야 저장 실패: '+error.message;
      if (error.message.includes('변경')) await readDepartment();
    }
  }

  async function fetchOfficialConstraints(id) {
    try {
      await write('/api/dashboard/related',{id});
      notify('공식 면허제한·참가가능지역·e발주 첨부 목록을 확인했습니다. 업체 자격은 별도 검토가 필요합니다.');
    } catch(error) {notify('공식 상세 API 조회 실패: '+error.message);}
  }

  async function enrichOne(id) {
    try {
      await write('/api/dashboard/enrich',{id});
      notify('공식 첨부 본문 확인을 실행했습니다. 결과의 추출 상태/출처를 확인하세요.');
    } catch(error) {notify('상세 본문 확인 실패: '+error.message);}
  }

  async function enrichBatch() {
    const b=byId('enrichBatch');
    b.disabled=true;
    try {
      const response=await write('/api/dashboard/enrich-batch',{});
      notify('상세 문서 '+response.attempted+'건 확인, 추출 성공 '+response.extracted+
       '건. 실패/미지원 문서는 검토대기로 유지합니다.');
    } catch(error) {notify('첨부 일괄 확인 오류: '+error.message);}
    finally {b.disabled=false;}
  }

  function offline(message) {
    connected = false;
    byId('storageMode').textContent = message + ' 아래 기존 목록은 합성 시안이며 실제 수집 공고가 아닙니다.';
    byId('collectionStatus').textContent = '공식 공고 서버 연결 실패';
  }

  function apply(state) {
    if (!state || !Number.isInteger(state.revision) || !Array.isArray(state.notices)
        || !Array.isArray(state.history) || !state.collection) throw Error('대시보드 응답 형식 오류');
    revision = state.revision;
    notices = state.notices;
    logs = state.history;
    if (!notices.some(n => n.id === selected)) selected = notices.length ? notices[0].id : null;
    document.body.dataset.bidSource = 'official';
    document.querySelector('#view-collection h1').textContent = '공식 입찰공고 수동 수집';
    document.querySelector('#view-collection .hgroup .desc').textContent = '최근 24시간 또는 7일을 선택해 공식 공고를 조회합니다. 정기 자동 수집은 구현 전입니다.';
    byId('storageMode').textContent = '나라장터 공식 API에서 수집한 데이터만 표시합니다. 자격·기술·원가·AI 적합도는 미검증 상태이며 담당자 결정은 별도 저장합니다.';
    document.querySelector('.stage').textContent = '공식 공고 목록';
    document.querySelector('.topright span').textContent = 'PC 로컬 저장';
    const detailBanner = document.querySelector('#view-full-detail .banner');
    detailBanner.querySelector('strong').textContent = '공식 목록 조회';
    detailBanner.querySelector('span').textContent = '수집된 공식 목록 메타데이터만 표시합니다. 원문/RFP, 법적 참가자격과 AI 분석 결과는 미확인입니다.';
    const collectionBanner = document.querySelector('#view-collection .banner');
    collectionBanner.querySelector('strong').textContent = '공식 API 수동 수집';
    collectionBanner.querySelector('span').textContent = 'API 인증키를 설정한 뒤 수집 버튼을 누르면 최근 용역 공고를 요청합니다. 정기 예약은 구현되지 않았습니다.';
    const cards = document.querySelectorAll('#view-collection .collectionGrid .card');
    cards[1].querySelector('h2').textContent = '수동 수집 (예약 없음)';
    cards[1].querySelector('p').textContent = '자동 수집 스케줄러는 아직 구현되지 않았습니다.';
    cards[2].querySelector('h2').textContent = state.collection.last_success || '실제 수집 기록 없음';
    cards[2].querySelector('p').textContent = state.collection.last_count === null ? '아직 조회 성공 기록 없음'
      : '검색 조건 해당 ' + state.collection.last_count + '건';
    const config = document.querySelectorAll('#view-collection .fieldset input');
    config[0].value = '조달청 나라장터 용역 공고 API';
    config[1].value = '수동 실행 · 정기 예약 미구현';
    document.querySelector('.footer').textContent = 'PUBLIC BID AGENT · LOCAL ONLY · OFFICIAL LIST METADATA · UNVERIFIED ELIGIBILITY · NO AUTOMATED BID SUBMISSION';
    byId('collectionStatus').textContent = '수집 상태: ' + state.collection.status
      + ' / 마지막 성공: ' + (state.collection.last_success || '없음')
      + ' / 최근 조회 범위: ' + (state.collection.lookback_days || '미확인') + '일'
      + ' / 해당 공고: ' + (state.collection.last_count ?? '미확인') + '건';
    byId('officialAdditionalFilters').hidden=false;
    renderNotices();
    if (page === 'full-detail') renderFullDetail();
    if (page === 'history') renderHistory();
  }

  async function reload() {
    const response = await fetch('/api/dashboard', {cache: 'no-store', headers: {Accept: 'application/json'}});
    if (!response.ok) throw Error('HTTP ' + response.status);
    const result = await response.json();
    if (result.storage !== 'LOCAL_JSON' || typeof result.csrf !== 'string') throw Error('로컬 저장 계약 오류');
    csrf = result.csrf;
    connected = true;
    apply(result.dashboard);
    byId('collect-action').disabled = !result.collection_available;
    byId('demo-collect').disabled = !result.collection_available;
    byId('collect-action').textContent = result.collection_available ? '공식 공고 지금 수집' : '공공데이터 API 키 필요';
    byId('demo-collect').textContent = result.collection_available ? '공식 공고 수집' : 'API 키 미설정';
    byId('assess-all').textContent = '미판단 공고 일괄 확인 보류';
    await refreshCredential();
    await readDepartment();
    await refreshRecommendations();
    await refreshRfpCoverage();
  }

  async function refreshCredential() {
    const response = await fetch('/api/procurement-key', {cache:'no-store', headers:{Accept:'application/json'}});
    if (!response.ok) throw Error('인증키 상태 확인 실패');
    const obj = await response.json();
    const credential = obj.credential;
    if (!credential || typeof credential.configured !== 'boolean') throw Error('인증키 설정 정보 오류');
    byId('procurementKeySettings').hidden = false;
    const source = credential.source === 'WINDOWS_DPAPI' ? '이 PC의 Windows 사용자 암호화 저장소'
      : credential.source === 'ENVIRONMENT' ? '서버 환경변수' : '미등록';
    byId('procurementKeyStatus').textContent = '현재 상태: ' + (credential.configured ? '등록됨' : '미등록')
      + ' / 저장 위치: ' + source + ' / 공식 연결 검증은 별도 버튼으로 확인하세요.';
    byId('procurementKeySave').disabled = !credential.can_save;
    byId('procurementKeyDelete').disabled = !credential.can_delete;
    byId('procurementKeyVerify').disabled = !credential.configured;
    byId('collect-action').disabled = !credential.configured;
    byId('demo-collect').disabled = !credential.configured;
    byId('collect-action').textContent = credential.configured ? '공식 공고 지금 수집' : '인증키 먼저 등록';
    byId('demo-collect').textContent = credential.configured ? '공식 공고 수집' : '인증키 미등록';
  }

  async function credentialAction(action) {
    const input = byId('procurementKeyInput');
    const status = byId('procurementKeyStatus');
    if (action === 'save' && !input.value.trim()) { status.textContent = '인증키를 먼저 입력하세요.'; input.focus(); return; }
    if (action === 'delete' && !window.confirm('이 PC에 저장된 나라장터 API 인증키를 삭제하시겠습니까?')) return;
    const buttons = ['procurementKeySave','procurementKeyVerify','procurementKeyDelete'].map(byId);
    buttons.forEach(button => button.disabled = true);
    try {
      const body = action === 'save' ? {key: input.value.trim()} : {};
      const response = await fetch('/api/procurement-key/' + action, {
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-Local-CSRF':csrf},
        body:JSON.stringify(body)
      });
      const data = await response.json();
      if (!response.ok || data.ok !== true) throw Error(data.error || '요청 실패 HTTP ' + response.status);
      await refreshCredential();
      const result = action === 'verify' ? '조달청 API 정상 응답 코드 00을 확인했습니다. 공고 수집은 별도로 실행하세요.'
        : action === 'save' ? '인증키를 이 PC 사용자 범위로 암호화 저장했습니다. 공식 연결 확인 버튼을 누르세요.'
        : '이 PC에 암호화 저장된 인증키를 삭제했습니다.';
      status.textContent = result;
      notify(result);
    } catch (error) {
      await refreshCredential().catch(() => {});
      status.textContent = '인증키 작업 실패: ' + error.message;
      notify('인증키 작업 실패: ' + error.message);
    } finally {
      input.value = '';
    }
  }

  async function write(path, payload) {
    const response = await fetch(path, {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json', 'X-Local-CSRF': csrf},
      body: JSON.stringify(payload)
    });
    const output = await response.json();
    if (!response.ok) {
      if (response.status === 409) await reload();
      throw Error(output.error || 'HTTP ' + response.status);
    }
    if (output.ok !== true || output.storage !== 'LOCAL_JSON') throw Error('서버 저장 응답 오류');
    apply(output.dashboard);
    return output;
  }

  async function decide(n, kind, reason = '') {
    try {
      await write('/api/dashboard/action', {expected_revision: revision, id: n.id, kind, reason});
      notify(kind === 'recommendation' ? '확인 보류를 기록했습니다. 실제 AI 판단이 아닙니다.'
        : '담당자 최종 결정과 사유를 PC에 저장했습니다.');
    } catch (e) {
      notify('기록 오류: ' + e.message);
    }
  }

  async function collectOfficial() {
    const button = byId('collect-action');
    button.disabled = true;
    try {
      await write('/api/dashboard/collect', {days: Number(byId('lookbackDays').value)});
      notify('나라장터 API 조회 결과를 갱신했습니다. 원문 및 실제 참가자격은 별도로 확인해야 합니다.');
    } catch (e) {
      try { await reload(); } catch (_) {}
      notify('공식 API 수집 실패. 기존 공고는 보존됩니다: ' + e.message);
    } finally {
      if (connected) button.disabled = false;
    }
  }

  const detailKVLocal = pairs => {
    const dl = el('dl', 'detailGrid');
    pairs.forEach(([key, value]) => dl.append(el('dt', '', key), el('dd', '', String(value ?? '미확인'))));
    return dl;
  };
  const linkOriginal = n => {
    if (!n.source_url) return null;
    const a = el('a', '', '공식 공고 원문 열기');
    a.href = n.source_url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    return a;
  };
  const btn = (label, fn, cls = '') => {
    const b = el('button', 'btn ' + cls, label);
    b.type = 'button';
    b.addEventListener('click', fn);
    return b;
  };

  const priorRenderDetail = window.renderDetail;
  window.renderDetail = function () {
    if (!connected) return priorRenderDetail();
    const n = getNotice(), pane = byId('detail');
    pane.replaceChildren();
    if (!n) { pane.append(el('p', 'muted', '공식 API에서 수집된 공고가 없습니다. 수집 상태를 확인하세요.')); return; }
    pane.append(el('h3', '', n.title), el('p', 'muted', '공식 목록 API · 원문/자격 미확인'));
    pane.append(detailKVLocal([['발주기관', n.org], ['공고번호/차수', n.bid_no + ' / ' + n.bid_order],
      ['공공조달 분류', n.procurement_classification || '미확인'],
      ['부서 분류', (n.department_categories||[]).join(', ')||'검토 필요'],
      ['사업 검토 상태', n.department_status || 'REVIEW'],
      ['입찰 기한 상태', n.window_status || 'UNKNOWN'],
       ['공식 정정·취소 상태', n.notice_lifecycle || '확인 전'],
       ['후속 차수 공고', n.superseded_by || '없음'],
       ['기존 RFP 근거', n.rfp_review_status === 'STALE' ? '최신성 재검증 필요' : '변경 감지 없음'],
      ['법적 참가 자격', '미확인'], ['예산 (API 원문값)', n.budget],
      ['마감 (API 원문값)', n.end], ['판단 권고', n.rec || '판단 전'],
      ['사람 최종결정', n.final || '미결정']]));
    if (linkOriginal(n)) pane.append(linkOriginal(n));
    const actions = el('div', 'actions');
    actions.append(btn('전체 상세보기', () => openFullDetail(n.id)),
      btn('자격 미확인 기록', () => void decide(n, 'recommendation'), 'primary'));
    pane.append(actions);
  };

  const priorFullDetail = window.renderFullDetail;
  window.renderFullDetail = function () {
    if (!connected) return priorFullDetail();
    const n = getNotice(), hero = byId('fullDetailHero'), pane = byId('fullDetailPane');
    hero.replaceChildren(); pane.replaceChildren();
    if (!n) { pane.append(el('p', '', '공고를 찾지 못했습니다.')); return; }
    byId('fullDetailTitle').textContent = n.title;
    hero.append(el('h2', '', n.org));
    hero.append(detailKVLocal([['공고번호', n.bid_no], ['공고 차수', n.bid_order],
      ['조달 분류', n.procurement_classification || '미확인'],
      ['부서 관심분야', (n.department_categories||[]).join(', ')||'분류 검토 필요'],
      ['부서 판단', n.department_status || 'REVIEW'],
      ['입찰 기한 상태', n.window_status || 'UNKNOWN'],
       ['공식 정정·취소 상태', n.notice_lifecycle || '확인 전'],
       ['후속 차수 공고', n.superseded_by || '없음'],
       ['기존 RFP 근거', n.rfp_review_status === 'STALE' ? '최신성 재검증 필요' : '변경 감지 없음'],
      ['법적 입찰 참가자격', '실제 업체 자격 미검증'],
      ['예산 API 값', n.budget], ['마감 API 값', n.end], ['API 관측 시각', n.observed_at]]));
    const tabs = byId('fullDetailTabs');
    tabs.querySelectorAll('[data-detail-tab]').forEach(b => {
      const active = b.dataset.detailTab === fullDetailTab;
      b.classList.toggle('active', active);
      b.setAttribute('aria-selected', String(active));
      b.tabIndex = active ? 0 : -1;
    });
    pane.append(el('div', 'detailNotice', '공식 목록 메타데이터만 검증 전 상태로 저장했습니다. 원문·자격·기술점수·이익률을 추정하지 않습니다.'));
     if (['CANCELLED','SUPERSEDED','REVIEW'].includes(n.notice_lifecycle))
       pane.append(el('div','detailNotice','공식 취소·후속차수·중복 차수로 자동 추천에서 제외됐습니다.'));
     if (n.rfp_review_status === 'STALE')
       pane.append(el('div','detailNotice','저장된 RFP는 이력으로 보존하며 최신성 재검증이 필요합니다.'));
    const section = detailBlock(fullDetailTab === 'overview' ? '공식 공고 기본정보' :
      fullDetailTab === 'requirements' ? '참가자격·과업 확인' :
      fullDetailTab === 'evaluation' ? '영향인자·원가 확인' : '참여 판단·담당자 결정');
    if (fullDetailTab === 'overview') {
      section.append(detailKVLocal([['사업명', n.title], ['발주기관', n.org], ['공고번호/차수', n.bid_no + '/' + n.bid_order],
        ['공고 종류', n.notice_kind || '미확인'],['공공조달 분류', n.procurement_classification || '미확인'],
        ['분류 번호', n.procurement_code || '미확인'],['정보화사업 여부', n.information_business || '미확인'],
        ['예산', n.budget], ['입찰 마감', n.end], ['입찰참가 등록 마감', n.qualification_deadline || '미확인'],
        ['문서 본문 상태', n.document_status || 'PENDING'],
        ['문서 출처', n.document_source_name || '아직 미확인']]));
      const a = linkOriginal(n); if (a) section.append(a);
      (n.attachments||[]).forEach(file=>{
        if(!file.url)return;
        const link=el('a','',file.name||'공고 규격서');
        link.href=file.url;link.target='_blank';link.rel='noopener noreferrer';
        const row=el('p','');row.append(link);section.append(row);
      });
      section.append(btn('공식 면허·지역·e발주 첨부 추가조회',()=>void fetchOfficialConstraints(n.id)));
      section.append(btn('공식 문서 본문 추출 후 다시 분류',()=>void enrichOne(n.id)));
      if(n.document_status==='FAILED')section.append(el('p','muted',n.document_error||'문서 추출 실패'));
      (n.document_evidence||[]).forEach(d => {
        section.append(el('p','muted','공식 문서: '+d.name+' / '+d.source+' / '+d.status+
          ' / 본문 '+(d.chars ?? '미추출')+'자 / SHA-256 '+(d.sha256||'미확인')));
        if(d.excerpt)section.append(el('p','muted','근거 발췌: '+d.excerpt.slice(0,360)));
      });
      if(n.rfp_text){
        const excerpt=el('pre','',n.rfp_text);
        excerpt.style.whiteSpace='pre-wrap';excerpt.style.overflowWrap='anywhere';
        excerpt.style.maxHeight='420px';excerpt.style.overflow='auto';
        section.append(el('h3','','공식 첨부에서 추출한 과업 내용 (최대 12,000자)'),excerpt);
      } else {
        section.append(el('p','muted','공고명·첨부파일명만으로 판정하지 않습니다. RFP 본문 추출 전입니다.'));
      }
    } else if (fullDetailTab === 'requirements') {
      section.append(detailKVLocal([['입찰공고 상태',n.notice_kind||'미확인'],
       ['입찰 마감',n.end],['참가자격 등록 마감',n.qualification_deadline||'미확인'],
       ['업종·면허 제한',n.industry_restriction||'미확인'],
       ['입찰 참가 제한',n.participation_restriction||'미확인'],
       ['법적 참가가능 여부','회사별 나라장터 등록·면허·실적 확인 전'],
       ['면허·지역 상세 API','조회: '+(n.related_status||'아직 미조회')]]));
      section.append(btn('공식 면허·지역·e발주 첨부 추가조회',()=>void fetchOfficialConstraints(n.id)));

      // 공식 문서의 원문 결속형 JSON 요구사항 후보를 사용자가 명시적으로 요청할 때만 확인.
      // 원본 PDF/HWP 페이지 번호는 기록되어 있지 않으므로 문자 위치만 표시한다.
      const requirementsPanel=detailBlock('공식 RFP 요구사항 구조화 (근거 확인)');
      const requirementsInfo=el('p','muted','8개 유형을 규칙으로 탐지합니다. 필수조건·업체 적격·원본 페이지는 확인이 필요합니다.');
      requirementsInfo.setAttribute('role','status');
      const requirementsRows=el('div','');
      const requirementsButton=btn('RFP 요구사항·출처 근거 확인',async()=>{
        requirementsButton.disabled=true;
        requirementsInfo.textContent='기존 비공개 RFP 청크 무결성을 확인하고 있습니다.';
        requirementsRows.replaceChildren();
        try{
          const response=await fetch('/api/dashboard/rfp-requirements?id='+encodeURIComponent(n.id),{cache:'no-store'});
          const payload=await response.json();
          if(!response.ok || !payload.requirements)throw Error(payload.error||'RFP 요구사항 검증 실패');
          const report=payload.requirements;
          requirementsInfo.textContent='상태 '+report.state+' / 사용한 검증 문서 '+report.sources_used+
            '개 / 근거 표현 후보 '+report.requirement_count+'건 / 분석 방식 '+report.analysis_mode+
            ' / 텍스트 범위 '+report.source_coverage+'. '+report.uncertainty;
          (report.warnings||[]).forEach(message=>requirementsRows.append(el('p','muted','주의: '+message)));
          (report.requirements||[]).forEach(category=>{
            const group=detailBlock(category.label+' · '+category.count+'건');
            if(!category.count)group.append(el('p','muted','탐지된 표현 없음. 실제 요건이 없다는 뜻은 아닙니다.'));
            (category.items||[]).forEach(item=>{
              const e=item.evidence;
              group.append(el('div','requirementRow',
                '' )); // 근거는 뒤이어 텍스트 노드로 안전하게 표시
              const row=group.lastElementChild;
              row.append(el('span','evidence',e.excerpt),
                el('span','muted','파일: '+e.file+' / SHA-256: '+e.source_sha256+
                  ' / 추출 텍스트 문자 위치 '+e.offset_start+'-'+e.offset_end+
                  ' / 페이지: 미확인 / 범위: '+e.source_mode+
                  ' / 판정: 원문 표현 후보 (사람 검증 필요)'));
            });
            requirementsRows.append(group);
          });
        }catch(error){requirementsInfo.textContent='구조화 근거 조회 실패: '+error.message;}
        finally{requirementsButton.disabled=false;}
      });
      requirementsPanel.append(requirementsInfo,requirementsButton,requirementsRows);
      section.append(requirementsPanel);

      // 사용자 요청 시에만 기존 RFP 본문에서 명시적 인력 요건 후보를 추출한다.
      const staffPanel=detailBlock('RFP 인력요건·부서 역량 예비 검토');
      const staffInfo=el('p','muted','검토 버튼을 누르면 공식 첨부 발췌에서 역할·등급·인원 후보를 찾습니다. 실제 참가자격·기술자 등급·가용 공수는 미확인입니다.');
      staffInfo.setAttribute('role','status');
      const staffRows=el('div','');
      const staffButton=btn('인력 요건 후보 확인',async()=>{
        staffButton.disabled=true;
        staffInfo.textContent='공식 RFP 발췌와 비공개 직무 집계를 읽고 있습니다.';
        staffRows.replaceChildren();
        try{
          const resp=await fetch('/api/dashboard/staffing?id='+encodeURIComponent(n.id),{cache:'no-store'});
          const payload=await resp.json();
          if(!resp.ok || !payload.staffing)throw Error(payload.error||'인력요건 조회 실패');
          const report=payload.staffing;
          staffInfo.textContent='발췌 분석 '+report.processed_document_count+'개 / 기록된 문서 증거 '+report.total_document_evidence_count+
            '개 / 생략 '+report.skipped_document_count+'개 (미추출·형식 '+report.skipped_nonextracted_or_invalid_count+
            '개, 처리 상한 '+report.skipped_due_to_limit_count+'개) / 각 발췌 최대 '+report.excerpt_char_limit+
            '자'+(report.any_text_truncated?' (본문 절단 있음)':' (본문 완전성 미확인)')+
            ' / 명시적 인력요건 후보 '+report.requirement_count+'건 / 인력 적격성 미확인. '+report.warning;
          if(!report.requirement_count){
            staffRows.append(el('p','muted',report.document_state==='NO_RFP_EXTRACTED'
              ?'추출된 공식 RFP 본문이 없습니다. 먼저 문서 본문을 추출해야 합니다.'
              :'현재 발췌 범위에 명시적으로 식별된 인력 요건이 없습니다. RFP 전체 표·각주를 확인하세요.'));
          }
          report.requirements.forEach(item=>{
            const row=el('div','requirementRow');
            const role=item.role==='analyst'?'분석가':'개발자';
            const grade={junior:'초급',intermediate:'중급',senior:'고급'}[item.grade]||'등급 불명';
            row.append(el('strong','',role+' / '+grade+' / '+item.headcount+(item.count_kind==='AT_LEAST'?'명 이상 (최소 인원)':'명 (원문 표기 인원)')),
              el('span','muted','기술 키워드: '+(item.skills.join(', ')||'추출 안 됨')),
              el('span','muted','내부 동명 등급 인원: '+
                (item.nominal_internal_grade_count===null?'프로필 미등록':item.nominal_internal_grade_count+'명')+
                ' (법정 등급·기술·투입 가능 여부 미확인)'),
              el('span','muted','저장된 문서 발췌: '+item.source_document+
                ' / 발췌 '+item.excerpt_line+'행 / 원본 페이지·표 위치 미확인'+
                ' / 기록된 문서 SHA-256(결속 미검증): '+(item.source_sha256||'저장된 해시 미기록 또는 형식 오류')+
                ' / 발췌 SHA-256: '+item.excerpt_sha256+
                ' / 출처 상태: '+item.source_status),
              el('span','evidence','개인정보를 제외한 탐지 표현: '+item.source_excerpt));
            staffRows.append(row);
          });
        }catch(error){staffInfo.textContent='인력요건 조회 실패: '+error.message;}
        finally{staffButton.disabled=false;}
      });
      staffPanel.append(staffInfo,staffButton,staffRows);
      section.append(staffPanel);

      if(n.related_status==='FETCHED'){
        const licenses=detailBlock('조달청 면허·업종 제한 (공식 목록)');
        if(!(n.license_restrictions||[]).length)licenses.append(el('p','muted','조회된 면허 제한 목록 없음 (업체 참가자격 확인과 별도)'));
        (n.license_restrictions||[]).forEach(x=>licenses.append(el('p','',x.name+' / '+x.allowed)));
        section.append(licenses);
        const regions=detailBlock('조달청 참가가능 지역');
        if(!(n.region_restrictions||[]).length)regions.append(el('p','muted','조회된 지역 제한 목록 없음 (다른 제한은 공고 원문 확인)'));
        (n.region_restrictions||[]).forEach(x=>regions.append(el('p','',x.name)));
        section.append(regions);
      }
      gates.forEach(([, label, evidence]) => {
        const row = el('div', 'requirementRow');
        row.append(el('strong', '', label), el('span', 'pill pending', '미확인'),
          el('span', 'evidence', '필요 서류: ' + evidence));
        section.append(row);
      });
    } else if (fullDetailTab === 'evaluation') {
      section.append(el('p','muted','공공조달 분류와 RFP 내용을 근거로 한 부서 관심분야: '+
        ((n.department_categories||[]).join(', ')||'미분류 / 상세 검토 필요')));
      (n.category_evidence||[]).forEach(e=>section.append(el('p','muted',
        e.category+' 근거: '+(e.sources||[]).join(', '))));
      section.append(el('p', 'muted', '기업 보유 역량·실적·원가와 RFP 원문 검증 전까지 점수를 계산하지 않습니다.'));
      factors.forEach(([, label]) => section.append(el('div', 'requirementRow', label + ' · 미확인')));
    } else {
      section.append(el('p', 'muted', '규칙 기반 보류 권고와 담당자 결정은 별개입니다. 사람의 결정에는 사유가 필요합니다.'));
      section.append(btn('증빙 미확인 권고 기록', () => void decide(n, 'recommendation')));
      const textarea = el('textarea', 'detailTextarea');
      textarea.id = 'fullDetailNoBidReason';
      textarea.maxLength = 500;
      textarea.placeholder = '담당자 결정 사유 입력 (필수)';
      section.append(textarea);
      const actions = el('div', 'actions');
      [['human_bid', '참여 결정'], ['human_no_bid', '불참 결정'], ['human_hold', '결정 보류']].forEach(([kind, label]) => {
        actions.append(btn(label, () => {
          if (!textarea.value.trim()) { notify('결정 사유를 입력하세요.'); textarea.focus(); return; }
          void decide(n, kind, textarea.value);
        }));
      });
      section.append(actions);
      const history = detailBlock('해당 공고 판단 이력');
      const entries = logs.filter(x => x.id === n.id);
      if (!entries.length) history.append(el('p', 'muted', '아직 저장된 판단 이력이 없습니다.'));
      entries.forEach(x => history.append(el('p', '', x.stamp + ' · ' + x.actor + ' · ' + x.reason + ' · ' + x.version)));
      section.append(history);
    }
    pane.append(section);
  };

  const priorAssess = window.assess;
  window.assess = function (n) {
    if (!connected) return priorAssess(n);
    return decide(n, 'recommendation');
  };
  const priorRecordNoBid = window.recordHumanNoBid;
  window.recordHumanNoBid = function (n, text) {
    if (!connected) return priorRecordNoBid(n, text);
    return decide(n, 'human_no_bid', text.trim());
  };

  function replaceClick(id, action) {
    const original = byId(id), fresh = original.cloneNode(true);
    original.replaceWith(fresh);
    fresh.addEventListener('click', action);
  }

  // 동일한 수집 관리 화면에 순차 RFP 분석 상태/작업 제어를 추가한다.
  const batchPanel=el('section','card');
  const batchTitle=el('h2','','공식 RFP 순차 분석 (서버 재시작 후 재개 가능)');
  const batchInfo=el('p','muted','작업을 시작하면 관심분야 후보를 대상으로 1건씩 추출합니다.');
  const batchSelect=el('select','');
  [1,3,10,25].forEach(v=>{
    const option=el('option','',v+'건 처리');
    option.value=String(v);option.selected=v===3;batchSelect.append(option);
  });
  const batchStart=btn('시작 / 재개',()=>void batchAction('start'));
  const batchPause=btn('현재 건 완료 후 중단',()=>void batchAction('pause'));
  const batchRetry=btn('실패 건만 선택 개수 재시도',()=>void batchAction('retry'));
  batchPanel.append(batchTitle,batchInfo,batchSelect,batchStart,batchPause,batchRetry);
  byId('view-collection').append(batchPanel);
  let previousBatch='';
  async function refreshBatch(){
    const response=await fetch('/api/rfp-batch',{cache:'no-store'});
    if(!response.ok)throw Error('RFP 배치 상태 조회 실패');
    const data=await response.json(),b=data.batch,s=b.statistics;
    batchInfo.textContent='상태 '+b.status+' / 대상 '+s.total+'건 / 성공 '+s.done+
      '건 / 실패 '+s.failed+'건 / 대기 '+s.pending+
      '건 / 순차 처리 간격 '+b.rate_limit_seconds+'초. 추출 성공은 법적 자격 확인이 아닙니다.';
    batchStart.disabled=b.status==='RUNNING';
    batchRetry.disabled=b.status==='RUNNING'||s.failed===0;
    batchPause.disabled=b.status!=='RUNNING';
    const signature=s.done+':'+s.failed;
    if(previousBatch && signature!==previousBatch)await reload();
    previousBatch=signature;
  }
  async function batchAction(action){
    [batchStart,batchPause,batchRetry].forEach(b=>b.disabled=true);
    try{
      const response=await fetch('/api/rfp-batch/'+action,{
        method:'POST',credentials:'same-origin',
        headers:{'Content-Type':'application/json','X-Local-CSRF':csrf},
        body:JSON.stringify({limit:Number(batchSelect.value)})
      });
      const result=await response.json();
      if(!response.ok)throw Error(result.error||'HTTP '+response.status);
      await refreshBatch();
    }catch(e){notify('RFP 분석 '+action+' 실패: '+e.message);}
    finally{await refreshBatch().catch(()=>{});}
  }
  // 실제 전체 공고 + 제한된 RFP 근거를 사용한 검토 우선순위. 법적 입찰추천 아님.
  const recommendationPanel=el('section','card');
  recommendationPanel.id='officialRecommendationPanel';
  const recommendationHeading=el('h2','','공고 분석 · 검토 추천 우선순위');
  const recommendationInfo=el('p','muted','공식 공고와 RFP 발췌를 검토 중입니다.');
  recommendationInfo.id='officialRecommendationInfo';
  recommendationInfo.setAttribute('role','status');
  const recommendationRows=el('div','');
  recommendationRows.id='officialRecommendationRows';
  const recommendationRefresh=btn('추천 검토 목록 새로고침',()=>void refreshRecommendations());
  recommendationPanel.append(recommendationHeading,recommendationInfo,
                             recommendationRefresh,recommendationRows);
  byId('view-collection').append(recommendationPanel);

  async function refreshRecommendations(){
    try{
      const r=await fetch('/api/dashboard/recommendations',
                          {cache:'no-store',headers:{Accept:'application/json'}});
      const response=await r.json();
      if(!r.ok || !response.recommendations)
        throw Error(response.error||'우선순위 계산 실패');
      const report=response.recommendations;
      recommendationInfo.textContent='전체 '+report.total_notices+'건 중 상세검토 우선 '+
        report.review_priority_count+'건 (RFP 발췌 확보 '+report.rfp_evidence_count+
        '건, 메타데이터 검토 '+report.metadata_only_count+
        '건). 순위는 입찰 적격·수익성·AI 최종 추천이 아닙니다.';
      recommendationRows.replaceChildren();
      if(!report.results.length){
        recommendationRows.append(el('p','muted','현재 마감 전 검토 후보가 없습니다. 부서 분야 설정과 RFP 추출 상태를 확인하세요.'));
        return;
      }
      report.results.forEach(item=>{
        const card=el('div','requirementRow');
        card.append(el('strong','',item.review_rank+'위 · '+item.title),
          el('span','muted',item.org+' / 마감 '+item.end+' / '+item.window_status),
          el('span','muted',item.priority_label+' · '+item.basis),
          el('span','muted','근거: '+(item.evidence.map(e=>e.category+' '+e.source).join(' · ')||'추가 확인 필요')),
          el('span','muted','참가자격 / 기술 적합성 / 가용인력 / 원가: 모두 미검증'));
        card.append(btn('공고 상세·RFP 확인',()=>{
          selected=item.id;openFullDetail(item.id);
        }));
        recommendationRows.append(card);
      });
    }catch(error){
      recommendationInfo.textContent='공고 우선순위 조회 실패: '+error.message;
      recommendationRows.replaceChildren();
    }
  }

  // RFP 추출을 늘리기 전 기존 공식 공고의 병목만 집계한다.
  const coveragePanel=el('section','card');
  coveragePanel.id='rfpCoveragePanel';
  const coverageTitle=el('h2','','RFP 원문 확보 현황과 다음 처리 대상');
  const coverageInfo=el('p','muted','수집 상태를 조회하고 있습니다.');
  coverageInfo.id='rfpCoverageInfo';
  coverageInfo.setAttribute('role','status');
  const coverageRows=el('div','');
  const coverageButton=btn('RFP 확보 현황 갱신',()=>void refreshRfpCoverage());
  coveragePanel.append(coverageTitle,coverageInfo,coverageButton,coverageRows);
  byId('view-collection').append(coveragePanel);
  async function refreshRfpCoverage(){
    try{
      const r=await fetch('/api/dashboard/rfp-coverage',{cache:'no-store'});
      const body=await r.json();
      if(!r.ok || !body.coverage)throw Error(body.error||'RFP 상태 조회 실패');
      const summary=body.coverage, st=summary.by_state_active;
      coverageInfo.textContent='부서 후보 전체 '+summary.candidate_count+
        '건 / 현재 마감 전 '+summary.active_candidate_count+
        '건 · 본문 확보 '+st.EXTRACTED_TEXT+'건';
      coverageRows.replaceChildren();
      [['READY_TO_FETCH','공식 문서 링크 있음 · 추출 대기'],
       ['FAILED_ATTEMPT','추출 실패 · 원인 확인'],
       ['UNSUPPORTED_FORMAT','지원되지 않는 첨부 형식'],
       ['MISSING_OFFICIAL_LINK','공식 첨부 링크 없음 · 상세조회 필요'],
       ['INVALID_ATTACHMENTS','첨부 목록 오류']].forEach(([key,label])=>{
          coverageRows.append(el('div','requirementRow',label+': '+st[key]+'건'));
       });
      coverageRows.append(el('p','muted','본문 확보는 과업 전체 검증 및 입찰 적격 판단과 별개입니다. 조회는 기존 파일을 수정하지 않습니다.'));
    }catch(error){
      coverageInfo.textContent='RFP 확보 현황 조회 실패: '+error.message;
      coverageRows.replaceChildren();
    }
  }

  // REVIEW 전수 수집 없이 공식 메타데이터 근거로 상세검토 순서만 제안.
  const discoveryPanel=el('section','card');
  const discoveryHeading=el('h2','','검토대기 공고 중 추가 발굴 (RFP 미확인)');
  const discoveryInfo=el('p','muted','전체 REVIEW 공고의 공식 조달분류/정보화사업/첨부 신호만 확인합니다.');
  const discoveryRows=el('div','');
  const discoveryRefresh=btn('검토 우선순위 갱신',()=>void refreshDiscovery());
  discoveryPanel.append(discoveryHeading,discoveryInfo,discoveryRefresh,discoveryRows);
  byId('view-collection').append(discoveryPanel);

  // 로컬 workforce.json만 조회한다. 공개 저장소에는 인원 코드와 등급을 넣지 않는다.
  const workforcePanel=el('div','card panel');
  workforcePanel.id='workforcePanel';
  workforcePanel.hidden=false;
  const workforceHeading=el('h2','','부서 인력·가정 원가 (PC 비공개)');
  const workforceInfo=el('p','helper','비공개 인력 정보는 조회 버튼을 누르면 이 PC에서만 읽습니다.');
  workforceInfo.setAttribute('role','status');
  const workforceRates=el('div','helper');
  const workforceRows=el('div','');
  const workforceRefresh=btn('인력 정보 조회',()=>void refreshWorkforce());
  workforcePanel.append(workforceHeading,workforceInfo,workforceRates,workforceRefresh,workforceRows);
  byId('view-collection').append(workforcePanel);
  const roleLabels={analyst:'분석가',developer:'개발자',executive:'임원',accounting:'경리'};
  const gradeLabels={junior:'초급',intermediate:'중급',senior:'고급'};
  const money=value=>Number(value).toLocaleString('ko-KR')+'원';
  async function refreshWorkforce(){
    workforcePanel.hidden=false;
    try{
      const response=await fetch('/api/workforce?detail=1',
        {cache:'no-store',headers:{'X-Local-CSRF':csrf}});
      if(!response.ok)throw Error('로컬 인력 상세 조회 미허용. 개인별 보기는 로컬 관리자 모드가 필요합니다.');
      const data=(await response.json()).workforce;
      workforceRows.replaceChildren();
      workforceRates.replaceChildren();
      if(!data){
        workforceInfo.textContent='로컬 workforce.json 미등록. 공개 저장소에는 실제 인력 자료를 보관하지 않습니다.';
        return;
      }
      workforceInfo.textContent='총 '+data.headcount_total+'명 / 분석·개발 '+data.delivery_headcount+
        '명 / 가정 연봉 합계 '+money(data.annual_assumed_salary_total_krw)+
        ' (급여 가정만 포함, 실제 회사 총원가·가용 공수 미확인)';
      workforceRates.textContent=data.roles.map(r=>r.role+' '+r.headcount+
        '명 · '+money(r.cost_per_mm_krw)+'/MM · '+(r.available_mm===null?'가용 MM 미정':'가용 '+r.available_mm+'MM')).join(' / ');
      data.staff.forEach(person=>{
        const box=el('div','requirementRow');
        const heading=person.id+' · '+(roleLabels[person.role]||'미확인')+
          (person.grade?' '+gradeLabels[person.grade]:'')+(person.lead?' (팀장)':'');
        box.append(el('strong','',heading),
          el('span','muted','담당분야: '+person.responsibility+' (임시 배정)'),
          el('span','muted','기술: '+(person.skills.join(', ')||'미등록')+
            ' / 기술 근거: '+(person.skills_evidence==='ASSUMED'?'추정':'미확인')+
            ' / 담당 근거: '+(person.responsibility_evidence==='ASSUMED'?'추정':'미확인')+
            ' / 가용 공수: '+(person.available_mm===null?'미정':person.available_mm+'MM')));
        workforceRows.append(box);
      });
    }catch(error){workforceInfo.textContent='인력 자료 조회 실패: '+error.message;}
  }

  async function refreshDiscovery(){
    try{
      const r=await fetch('/api/dashboard/discovery',{cache:'no-store'});
      if(!r.ok)throw Error('검토대기 우선순위 조회 실패');
      const data=(await r.json()).discovery;
      discoveryInfo.textContent='전체 검토대기 '+data.total_review+'건 중 메타데이터 재검토 '+
        data.priority_count+'건. 표시 상위 '+data.results.length+
        '건. 과업·개발비중·참가자격은 RFP 확인 전까지 미확인입니다.';
      discoveryRows.replaceChildren();
      data.results.forEach(item=>{
        const row=el('div','requirementRow');
        row.append(el('strong','',item.title),
          el('span','muted','우선순위 '+item.score+' / '+item.window_status+
            ' / 참가자격 '+item.eligibility));
        row.append(el('span','muted','근거: '+item.evidence.map(e=>e.source+
          ' ('+e.weight+')').join(' · ')));
        row.append(btn('기존 상세에서 확인',()=>{
          selected=item.id; openFullDetail(item.id);
        }));
        discoveryRows.append(row);
      });
    }catch(error){discoveryInfo.textContent='검토대기 재분류 조회 오류: '+error.message;}
  }

  setInterval(()=>{if(connected)void refreshBatch().catch(()=>{});},4000);

  byId('departmentView').addEventListener('change',()=>renderNotices());
  byId('deadlineView').addEventListener('change',()=>renderNotices());
  byId('departmentSave').addEventListener('click',()=>void saveDepartment());
  byId('enrichBatch').addEventListener('click',()=>void enrichBatch());
  byId('departmentReclassify').addEventListener('click',async()=>{
    const b=byId('departmentReclassify');b.disabled=true;
    try{const result=await write('/api/dashboard/reclassify',{});
      notify('수집 공고 '+result.updated+'건을 부서 기준으로 다시 분류했습니다.');}
    catch(error){notify('전체 재분류 실패: '+error.message);}
    finally{b.disabled=false;}
  });
  reload().then(() => {
    void refreshBatch().catch(()=>{});
    void refreshDiscovery();
    // 비공개 인력 조회는 사용자 버튼 클릭 시에만 실행한다.
    byId('procurementKeySave').addEventListener('click', () => void credentialAction('save'));
    byId('procurementKeyVerify').addEventListener('click', () => void credentialAction('verify'));
    byId('procurementKeyDelete').addEventListener('click', () => void credentialAction('delete'));
    replaceClick('demo-collect', () => void collectOfficial());
    replaceClick('collect-action', () => void collectOfficial());
    replaceClick('assess-all', async () => {
      const pending = notices.filter(n => !n.rec).slice(0, 20);
      for (const n of pending) await decide(n, 'recommendation');
      if (!pending.length) notify('판단 대기 공고가 없습니다.');
    });
    replaceClick('detailAssess', () => {
      const n = getNotice();
      if (n) void decide(n, 'recommendation');
    });
  }).catch(e => {
    offline('대시보드 API 연결 오류: ' + e.message);
    notify('실제 데이터 연결 실패: ' + e.message);
  });
})();
