/** P07 로컬 UI 합성 DOM 계약: 외부 fetch·실제 사용자 문서 없이 텍스트/앵커/초안 분리를 검증. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; this.style = {}; this.dataset = {}; }
  append(...children) { this.children.push(...children); }
  prepend(...children) { this.children.unshift(...children); }
  replaceChildren(...children) { this.children = children; this.textContent = ''; }
  addEventListener() {}
  set innerHTML(_) { throw Error('HTML rendering is forbidden'); }
}
function text(node) { return node.textContent + node.children.map(text).join('\n'); }
function all(node) { return [node, ...node.children.flatMap(all)]; }
function setup() {
  const nodes = new Map();
  const context = {window:{}, document:{
    createElement:tag=>new Element(tag),
    getElementById:id=>{ if (!nodes.has(id)) nodes.set(id, new Element('div')); return nodes.get(id); }
  }, fetch:()=>new Promise(()=>{})}; // 초기 조회는 대기 상태로 유지; 네트워크 사용 없음.
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../local_app/app.js'), 'utf8'), context);
  return {context, nodes};
}

test('missing and mismatched sources remain explicitly uncertain', () => {
  const {context} = setup();
  for (const status of ['MISSING', 'MISMATCH', 'UNKNOWN']) {
    const root = new Element('section');
    context.renderDraftSources(root, {status, links:[]});
    assert.match(text(root), /출처 없음|출처 불일치/);
    assert.equal(all(root).filter(x=>x.tag==='a').length, 0);
  }
});

test('matched source renders literal text, local anchor, and partial extraction warning', () => {
  const {context} = setup();
  const root = new Element('section');
  context.renderDraftSources(root, {status:'EXTRACTED_TEXT_MATCH_ONLY', links:[{
    source_id:'document:0', name:'<img src=x onerror=alert(1)>', quote:'<script>untrusted()</script>',
    offset_start:3, offset_end:35, text_sha256:'a'.repeat(64), partial:true,
    url:'javascript:alert(1)', page:5
  }, {source_id:'javascript:alert(1)', quote:'ignore'}]});
  assert.match(text(root), /원문 의미 미검증/);
  assert.match(text(root), /잘림 또는 파서 경고/);
  assert.match(text(root), /원본 페이지 미확인/);
  assert.match(text(root), /<script>untrusted\(\)<\/script>/);
  assert.deepEqual(all(root).filter(x=>x.tag==='a').map(x=>x.href), ['#draft-source-document-0']);
  assert.equal(all(root).filter(x=>x.tag==='script'||x.tag==='img').length, 0);
});

test('fallback and changed input are DRAFT while human final decision stays separate', () => {
  const {context, nodes} = setup();
  context.sample = {id:'synthetic', title:'합성', prompt:'', documents:[], ai_reports:{},
    gates:{}, factors:{}, decision:'no_bid', reason:'사용자 판단',
    decision_support:{status:'HOLD_UNVERIFIED', title:'참여 판단 보류', analysis_mode:'RULE_BASED_FALLBACK',
      draft_context_status:'CHANGED', uncertainty:['회사 자격 미검증'], flags:[],
      source_checks:{recommendation:{status:'MISSING',links:[]}}}};
  vm.runInContext('active=sample; render();', context);
  const output = text(nodes.get('decisionSupport'));
  assert.match(output, /DRAFT/);
  assert.match(output, /규칙 기반 fallback/);
  assert.match(output, /분석 입력 변경/);
  assert.match(output, /사용자 최종 결정\(별도\): no_bid/);
  assert.equal(context.sample.decision, 'no_bid');
});

test('input cap shows partial ranges and omitted documents without interpreting HTML', () => {
  const {context, nodes} = setup();
  context.sample = {id:'synthetic', title:'합성', prompt:'', documents:[], ai_reports:{},
    gates:{}, factors:{}, decision:'no_bid', reason:'사용자 판단', history:[{decision:'no_bid'}],
    decision_support:{status:'HOLD_INPUT_INCOMPLETE', analysis_mode:'RULE_BASED_FALLBACK',
      draft_context_status:'CURRENT', flags:[], input_coverage:{incomplete:true, sources:[
        {source_id:'document:1', name:'partial.txt', status:'TRUNCATED', transmitted_start:0, transmitted_end:1697, total_chars:44000},
        {source_id:'document:2', name:'<script>omitted()</script>', status:'OMITTED', transmitted_start:0, transmitted_end:0, total_chars:29}
      ]}}};
  const before = JSON.stringify(context.sample);
  vm.runInContext('active=sample; render();', context);
  const root = nodes.get('decisionSupport');
  assert.match(text(root), /모델 입력 잘림·누락/);
  assert.match(text(root), /AI 조건·점수 제외/);
  assert.match(text(root), /partial.txt: 일부 잘림 · 전달 범위 0–1697 \/ 전체 44000자/);
  assert.match(text(root), /<script>omitted\(\)<\/script>: 전체 누락 · 전달 범위 0–0/);
  assert.match(text(root), /사용자 최종 결정\(별도\): no_bid/);
  assert.equal(all(root).filter(x=>x.tag==='script').length, 0);
  assert.equal(JSON.stringify(context.sample), before);
});

test('matching citation distinguishes model input truncation from parser warnings', () => {
  const {context} = setup();
  const root = new Element('section');
  context.renderDraftSources(root, {status:'EXTRACTED_TEXT_MATCH_ONLY', links:[{
    source_id:'document:1', name:'partial.txt', quote:'synthetic',
    offset_start:0, offset_end:9, text_sha256:'b'.repeat(64), partial:true, input_truncated:true
  }]});
  assert.match(text(root), /모델 입력 잘림/);
  assert.doesNotMatch(text(root), /파서 경고/);
});
