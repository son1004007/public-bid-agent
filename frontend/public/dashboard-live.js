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
  let departmentProfile = {revision:0,categories:['AI','SW','DATA','SECURITY'],include_review:true};

  // 기본은 마감 전·확인필요만 표시하되, 모든 API 원본을 DB에 그대로 남긴다.
  window.officialListFilter = function(n) {
    const deadline = byId('deadlineView').value;
    const windowStatus = n.window_status || 'UNKNOWN';
    if (deadline !== 'all' && (windowStatus === 'CANCELLED' || windowStatus === 'CLOSED')) return false;
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
      section.append(btn('공식 문서 본문 추출 후 다시 분류',()=>void enrichOne(n.id)));
      if(n.document_status==='FAILED')section.append(el('p','muted',n.document_error||'문서 추출 실패'));
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
       ['법적 참가가능 여부','회사별 나라장터 등록·면허·실적 확인 전']]));
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
