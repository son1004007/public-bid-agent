/** 구형 검증 플래그 합성 DOM 회귀: 네트워크 없이 실제 render의 지표/체크박스와 입력 불변을 검증한다. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() { this.children = []; this.textContent = ''; this.style = {}; this.dataset = {}; }
  append(...children) { this.children.push(...children); }
  prepend(...children) { this.children.unshift(...children); }
  replaceChildren(...children) { this.children = children; this.textContent = ''; }
  addEventListener() {}
  set innerHTML(_) { throw Error('HTML rendering is forbidden'); }
}
function all(node) { return [node, ...node.children.flatMap(all)]; }
function setup(evidence) {
  const nodes = new Map();
  const gateKeys = ['eligibility', 'licenses', 'track_record', 'resources', 'teaming', 'deadline', 'security', 'contract'];
  const factorKeys = ['technical', 'staff', 'experience', 'buyer', 'competition', 'differentiation', 'profit',
    'bid_cost', 'relationship', 'strategy', 'readiness', 'risk'];
  const weights = [15, 10, 10, 10, 10, 10, 10, 5, 5, 5, 5, 5];
  const sample = {id:'synthetic', title:'합성 구형 검증', prompt:'', documents:[], ai_reports:{},
    gates:Object.fromEntries(gateKeys.map(key=>[key, {status:'pass', evidence, verified:true}])),
    factors:Object.fromEntries(factorKeys.map(key=>[key, {score:5, evidence, verified:true}])),
    decision:'no_bid', reason:'합성 최종 사유', history:[{decision:'no_bid', reason:'합성 이력'}]};
  const context = {sample, gateDefs:gateKeys.map(key=>[key, key]),
    factorDefs:factorKeys.map((key, i)=>[key, key, weights[i]]), window:{}, document:{
      createElement:()=>new Element(),
      getElementById:id=>{ if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); }
    }, fetch:()=>new Promise(()=>{})}; // 초기 조회를 정지하며 네트워크 호출은 수행하지 않는다.
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../local_app/app.js'), 'utf8'), context);
  function render() {
    const before = JSON.stringify(sample);
    vm.runInContext('gates=gateDefs; factors=factorDefs; active=sample; render();', context);
    assert.equal(JSON.stringify(sample), before);
    return nodes.get('review').textContent;
  }
  const checked = group=>all(nodes.get(group)).filter(node=>node.type==='checkbox' && node.checked).length;
  return {sample, render, checked};
}

test('legacy blank evidence withholds 100/100 and all verification checkmarks', () => {
  for (const evidence of ['', '   ', '\t\r\n', '\u00a0\u3000', '\u0085\u001c', '\ufeff']) {
    const ui = setup(evidence);
    const output = ui.render();
    assert.match(output, /미검증 Gate 8개 \/ 미검증 요인 12개/);
    assert.match(output, /참고 가중지표: 미산출/);
    assert.match(output, /최종 결정: no_bid/);
    assert.doesNotMatch(output, /100\.0\/100/);
    assert.equal(ui.checked('gates'), 0);
    assert.equal(ui.checked('factors'), 0);
  }
});

test('valid evidence retains score and na, factor-only gaps and unbacked failures withhold it', () => {
  const ui = setup('  합성 근거  ');
  ui.sample.gates.teaming.status = 'na';
  assert.match(ui.render(), /100\.0\/100/);
  assert.equal(ui.checked('gates'), 8);
  assert.equal(ui.checked('factors'), 12);
  ui.sample.factors.technical.evidence = ' ';
  assert.match(ui.render(), /미검증 Gate 0개 \/ 미검증 요인 1개/);
  assert.match(ui.render(), /참고 가중지표: 미산출/);
  ui.sample.gates.licenses = {status:'fail', evidence:' ', verified:true};
  assert.match(ui.render(), /필수 미충족: 확정 없음/);
  assert.equal(ui.checked('gates'), 7);
  ui.sample.gates.licenses.evidence = '합성 미충족 근거';
  assert.match(ui.render(), /필수 미충족: licenses/);
  assert.match(ui.render(), /참고 가중지표: 미산출/);
});

test('strict flag, evidence type, gate status and factor score checks fail closed', () => {
  for (const change of [{verified:'true'}, {verified:1}, {verified:false}, {evidence:null}, {evidence:123}]) {
    const ui = setup('합성 근거');
    Object.assign(ui.sample.gates.licenses, change);
    Object.assign(ui.sample.factors.technical, change);
    assert.match(ui.render(), /미검증 Gate 1개 \/ 미검증 요인 1개/);
    assert.match(ui.render(), /참고 가중지표: 미산출/);
  }
  for (const status of ['unknown', 'invalid', null]) {
    const ui = setup('합성 근거');
    ui.sample.gates.licenses.status = status;
    assert.match(ui.render(), /미검증 Gate 1개/);
  }
  for (const score of [null, true, '5', 0, 6]) {
    const ui = setup('합성 근거');
    ui.sample.factors.technical.score = score;
    assert.match(ui.render(), /미검증 요인 1개/);
  }
});
