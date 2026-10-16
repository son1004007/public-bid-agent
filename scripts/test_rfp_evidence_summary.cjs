/** RFP 화면 텍스트 계약만 검증. 외부 서버·개인 문서·브라우저 권한 불필요. */
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../frontend/public/rfp-evidence-summary.js'), 'utf8');
const browser = {window: {}};
vm.runInNewContext(source, browser, {filename:'rfp-evidence-summary.js'});
const view = browser.window.rfpEvidenceSummary;
assert.ok(view && typeof view.summary === 'function');

test('new schema reports exact bounded omissions', () => {
  const report = {requirement_count: 5, omitted_candidate_count: 3, sources_used: 1,
    state: 'EVIDENCE_CANDIDATES', uncertainty: '사람 검증'};
  assert.match(view.summary(report), /표시 5건 · 표시 상한 생략 3건/);
  assert.match(view.category({label:'입찰참가자격',count:5,omitted_count:3}), /상한 생략 3건/);
  assert.equal(view.category({label:'평가기준',count:2,omitted_count:0}), '평가기준 · 표시 2건');
});

test('old API and blocked response do not falsely report zero omissions', () => {
  assert.match(view.summary({requirement_count: 2,sources_used: 1,state:'EVIDENCE_CANDIDATES'}),
    /표시 상한 생략 미확인/);
  assert.match(view.category({label:'과업',count:2}), /상한 생략 미확인/);
  const blocked={requirement_count:0,omitted_candidate_count:0,sources_used:0,state:'STALE_RFP'};
  assert.match(view.summary(blocked), /표시 0건 · 표시 상한 생략 0건/);
});

test('malformed, negative and unsafe counts remain unknown', () => {
  for (const val of [null,undefined,-1,2.5,'9',Number.MAX_SAFE_INTEGER+1,NaN,Infinity]) {
    assert.equal(view.count(val),'미확인');
    assert.match(view.category({label:'기술요건',count:2,omitted_count:val}), /상한 생략 미확인/);
  }
});
