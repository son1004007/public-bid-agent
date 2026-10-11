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
    byId('storageMode').textContent = '나라장터 공식 API에서 수집한 데이터만 표시합니다. 자격·기술·원가·AI 적합도는 미검증 상태이며 담당자 결정은 별도 저장합니다.';
    document.querySelector('.stage').textContent = '공식 공고 목록';
    document.querySelector('.topright span').textContent = 'PC 로컬 저장';
    byId('collectionStatus').textContent = '수집 상태: ' + state.collection.status
      + ' / 마지막 성공: ' + (state.collection.last_success || '없음')
      + ' / 해당 공고: ' + (state.collection.last_count ?? '미확인') + '건';
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
      await write('/api/dashboard/collect', {});
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
      ['예산 (API 원문값)', n.budget], ['마감 (API 원문값)', n.end],
      ['판단 권고', n.rec || '판단 전'], ['사람 최종결정', n.final || '미결정']]));
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
        ['예산', n.budget], ['입찰 마감', n.end], ['첨부·RFP', '미수집 / 미확인']]));
      const a = linkOriginal(n); if (a) section.append(a);
    } else if (fullDetailTab === 'requirements') {
      gates.forEach(([, label, evidence]) => {
        const row = el('div', 'requirementRow');
        row.append(el('strong', '', label), el('span', 'pill pending', '미확인'),
          el('span', 'evidence', '필요 서류: ' + evidence));
        section.append(row);
      });
    } else if (fullDetailTab === 'evaluation') {
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

  reload().then(() => {
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
