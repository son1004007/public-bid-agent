/** RFP 후보 표시 상한 상태의 안전한 문자열 포맷. 법적 적격성·전체 누락률로 해석하지 않는다.
 * 입력: 서버 JSON의 후보 수/생략 수. 출력: 화면에 textContent로 표시할 단순 텍스트.
 * 신뢰 경계: 숫자가 없거나 손상되면 0으로 조용히 바꾸지 않고 미확인으로 보인다.
 * 부작용: 없음. 원본·외부 통신·사용자 판단 변경 없음.
 */
(function (root) {
  'use strict';
  function count(value, unit = '') {
    return Number.isSafeInteger(value) && value >= 0 ? String(value) + unit : '미확인';
  }
  function summary(report) {
    const data = report || {};
    const state = typeof data.state === 'string' ? data.state : 'UNKNOWN';
    const uncertainty = typeof data.uncertainty === 'string' ? data.uncertainty : '사람 검증 필요';
    return '원문 표현 후보 표시 ' + count(data.requirement_count, '건') +
      ' · 표시 상한 생략 ' + count(data.omitted_candidate_count, '건') +
      ' · 검증된 문서 ' + count(data.sources_used, '개') +
      ' · 상태 ' + state + '. ' + uncertainty;
  }
  function category(group) {
    const data = group || {};
    const extra = count(data.omitted_count, '건');
    return String(data.label || '미확인 유형') + ' · 표시 ' + count(data.count, '건') +
      (extra === '0건' ? '' : ' · 상한 생략 ' + extra);
  }
  const api = Object.freeze({ count, summary, category });
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.rfpEvidenceSummary = api;
})(typeof window === 'undefined' ? globalThis : window);
