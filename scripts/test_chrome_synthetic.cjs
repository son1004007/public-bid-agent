/**
 * P09 Chrome 합성 E2E 설계 계약.
 * 목적: 실제 localhost UI의 BID-03 세 큐·390/1440px 및 기존 파일 선택·수기 이력을 검증한다.
 * 입력/출력: Python fixture와 새 Chrome 프로필만 사용하고 PASS/실패 단계를 출력한다.
 * 신뢰 경계: 기존 브라우저/운영 서버/자료 경로를 받지 않는다. 외부 페이지 요청은 차단한다.
 * 부작용: 자신이 만든 자식 프로세스·임시 Chrome 프로필만 종료/정리한다.
 * 실패/시간 제한: CDP 10초, 조건 대기 15초, 전체 90초. 재시도로 실패를 숨기지 않는다.
 * 불변조건: sandbox/TLS/CSP를 완화하지 않으며 사용자 UI 승인/배포를 주장하지 않는다.
 * 관련: local_app/test_local_acceptance.py, docs/reviews/P09_SYNTHETIC_ACCEPTANCE_2026-10-18.md.
 */
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createInterface} = require('node:readline');
const {setTimeout: delay} = require('node:timers/promises');

const repo = path.resolve(__dirname, '..');
const chromePath = process.env.P09_CHROME || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const pythonPath = process.env.P09_PYTHON || 'python';

class CDP {
  constructor(child) {
    this.child = child; this.next = 0; this.pending = new Map(); this.listeners = []; this.closed = false;
    let buffered = '';
    child.stdio[4].setEncoding('utf8');
    child.stdio[4].on('data', data => {
      buffered += data;
      let end;
      while ((end = buffered.indexOf('\0')) !== -1) {
        const message = JSON.parse(buffered.slice(0, end)); buffered = buffered.slice(end + 1);
        if (message.id) {
          const pending = this.pending.get(message.id);
          if (!pending) continue;
          this.pending.delete(message.id); clearTimeout(pending.timer);
          if (message.error) pending.reject(Error(`CDP ${pending.method}: ${message.error.message}`));
          else pending.resolve(message.result);
        } else this.listeners.forEach(listener => listener(message));
      }
    });
    const stop = reason => {
      this.closed = true;
      for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(Error(reason)); }
      this.pending.clear();
    };
    child.on('exit', (code, signal) => stop(`Chrome exited (${code ?? signal})`));
    child.on('error', () => stop('Chrome launch failed'));
    child.stdio[3].on('error', () => stop('Chrome command pipe closed'));
    child.stdio[4].on('error', () => stop('Chrome response pipe closed'));
  }
  send(method, params = {}, sessionId) {
    if (this.closed) return Promise.reject(Error('Chrome already exited'));
    const id = ++this.next;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(Error(`CDP timeout: ${method}`)); }, 10000);
      this.pending.set(id, {resolve, reject, timer, method});
      this.child.stdio[3].write(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}) + '\0');
    });
  }
}

async function waitFor(check, label, timeout = 15000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await check()) return;
    await delay(100);
  }
  throw Error(`Timed out: ${label}`);
}

async function main() {
  assert(fs.existsSync(chromePath), 'BLOCKED: Chrome binary unavailable; set P09_CHROME');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'p09-chrome-'));
  let fixture, chrome, cdp, fixtureInfo, fixtureClosed, chromeClosed, fixtureExit;
  let stage = 'startup';
  const lines = [];
  let fatal;
  const watchdog = setTimeout(() => {
    fatal = Error('E2E exceeded 90 seconds');
    chrome?.kill(); fixture?.kill();
  }, 90000);
  try {
    fixture = spawn(pythonPath, ['-u', 'local_app/test_local_acceptance.py', '--serve-chrome'],
      {cwd: repo, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'], env: {...process.env, PYTHONUTF8: '1'}});
    fixture.on('error', () => { fatal = Error('BLOCKED: Python fixture could not start'); });
    fixture.stdin.on('error', () => { fatal ||= Error('Synthetic fixture input closed'); });
    fixtureClosed = new Promise(resolve => fixture.once('close', code => { fixtureExit = code; resolve(code); }));
    const reader = createInterface({input: fixture.stdout});
    reader.on('line', line => { lines.push(line); if (!fixtureInfo && line.startsWith('{')) fixtureInfo = JSON.parse(line); });
    // This process only handles generated fixtures; keep diagnostics bounded.
    fixture.stderr.on('data', () => { fatal ||= Error('Synthetic Python fixture emitted an error'); });
    await waitFor(() => { if (fatal) throw fatal; return fixtureInfo; }, 'synthetic server startup');
    assert.match(fixtureInfo.base, /^http:\/\/127\.0\.0\.1:\d+$/);
    chrome = spawn(chromePath, ['--headless', '--remote-debugging-pipe', `--user-data-dir=${profile}`,
      '--no-first-run', '--no-default-browser-check', '--disable-background-networking', 'about:blank'],
      {windowsHide: true, stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe']});
    chrome.stderr.on('data', data => {
      // Only fixed diagnostics, never arbitrary browser logs/profile paths.
      const text=String(data);
      for (const marker of ['Access is denied', 'Permission denied', 'sandbox', 'Bad file descriptor']) {
        if (text.includes(marker)) console.error(`Chrome diagnostic: ${marker}`);
      }
    });
    chrome.on('error', () => { fatal = Error('BLOCKED: Chrome launch failed'); });
    chromeClosed = new Promise(resolve => chrome.once('close', resolve));
    cdp = new CDP(chrome);
    const version = await cdp.send('Browser.getVersion');
    console.log(`Chrome synthetic E2E: ${version.product}; Node ${process.version}`);
    const {targetId} = await cdp.send('Target.createTarget', {url: 'about:blank'});
    const {sessionId} = await cdp.send('Target.attachToTarget', {targetId, flatten: true});
    const send = (method, params) => cdp.send(method, params, sessionId);
    const external = []; const errors = []; let loads = 0;
    cdp.listeners.push(message => {
      if (message.sessionId !== sessionId) return;
      if (message.method === 'Page.loadEventFired') loads += 1;
      if (message.method === 'Runtime.exceptionThrown') errors.push('Uncaught page exception');
      if (message.method === 'Fetch.requestPaused') {
        const {requestId, request} = message.params;
        const local = new URL(request.url).origin === fixtureInfo.base;
        if (!local) external.push('External page request blocked');
        send(local ? 'Fetch.continueRequest' : 'Fetch.failRequest',
          local ? {requestId} : {requestId, errorReason: 'BlockedByClient'}).catch(e => { fatal = e; });
      }
    });
    await send('Runtime.enable'); await send('Page.enable');
    await send('Fetch.enable', {patterns: [{urlPattern: '*'}]});
    const evaluate = async expression => {
      if (fatal) throw fatal;
      const result = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
      assert(!result.exceptionDetails, `Page evaluation failed at ${stage}`);
      return result.result.value;
    };
    const click = async expression => {
      const point = await evaluate(`(() => { const e=(${expression}); if(!e||e.disabled)return null;
        e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect();
        return {x:r.x+r.width/2,y:r.y+r.height/2}; })()`);
      assert(point, `Missing/enabled control at ${stage}`);
      await send('Input.dispatchMouseEvent', {type: 'mousePressed', button: 'left', clickCount: 1, ...point});
      await send('Input.dispatchMouseEvent', {type: 'mouseReleased', button: 'left', clickCount: 1, ...point});
    };
    const button = label => `[...document.querySelectorAll('button')].find(e=>e.textContent.trim()===${JSON.stringify(label)})`;
    const textIncludes = text => evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`);
    const openDetail = async () => {
      await waitFor(() => textIncludes('P09 합성 SW 사업'), 'synthetic notice');
      await click(button('전체 상세보기'));
      await waitFor(() => evaluate(`document.querySelector('#fullDetailTitle').textContent.includes('P09 합성')`), 'detail');
    };
    stage = 'list/detail/XSS';
    const initialLoad = loads;
    await send('Page.navigate', {url: fixtureInfo.base + '/decision-preview'});
    await waitFor(() => loads > initialLoad, 'initial page load');
    stage = 'BID-03 desktop/mobile shortlist';
    await waitFor(() => evaluate(`document.body.dataset.bidSource==='official'`), 'official synthetic dashboard');
    for (const width of [1440,390]) {
      await send('Emulation.setDeviceMetricsOverride', {width,height:900,deviceScaleFactor:1,mobile:width===390});
      await click(`document.querySelector('[data-view="bid-now"]')`);
      await waitFor(() => evaluate(`document.querySelectorAll('#bidNowRows .bidNowRow').length===1`), 'matching queue');
      assert(await textIncludes('법적 적격 미검증 (UNVERIFIED)'));
      assert(await textIncludes('보완 후 마진 미검증 (UNVERIFIED)'));
      assert(await textIncludes('취소·구차수·공식 상태 확인 보류 2건'));
      assert(await textIncludes('마감·접수 종료 보류 1건'));
      assert(await textIncludes('텍스트 잘림 보고') || await textIncludes('본문 참조 무결성 미검증'));
      for (const [queue,expected] of [['augmentation_review_results','역량 보완·비용 차감 후 수익 검토'],
        ['registration_review_results','등록기한 경과']]) {
        await evaluate(`(() => { const q=document.querySelector('#bidNowQueue');q.value=${JSON.stringify(queue)};
          q.dispatchEvent(new Event('change',{bubbles:true})); })()`);
        await waitFor(() => textIncludes(expected), queue);
        assert.equal(await evaluate(`document.querySelectorAll('#bidNowRows .bidNowRow').length`),1);
      }
      assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), `${width}px shortlist overflow`);
      if(process.env.BID03_SCREENSHOTS) {
        fs.mkdirSync(process.env.BID03_SCREENSHOTS,{recursive:true});
        const capture=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        fs.writeFileSync(path.join(process.env.BID03_SCREENSHOTS,`bid03-${width}.png`),Buffer.from(capture.data,'base64'));
      }
      // Re-enter resets neither selected queue nor old lists; choose matching before detail.
      await evaluate(`(() => { const q=document.querySelector('#bidNowQueue');q.value='matching_results';
        q.dispatchEvent(new Event('change')); })()`);
      await click(button('기존 상세·기한·사람 판단 확인'));
      await waitFor(() => evaluate(`document.querySelector('#view-full-detail').classList.contains('active')`), 'existing detail from shortlist');
      await click(`document.querySelector('[data-view="notices"]')`);
      console.log(`PASS BID03 ${width}px: three queues/holds/UNVERIFIED/detail/no overflow`);
    }
    await send('Emulation.setDeviceMetricsOverride', {width:1440,height:900,deviceScaleFactor:1,mobile:false});
    await openDetail();
    assert.equal(await evaluate('window.p09Injected === true'), false);
    assert.equal(await evaluate(`document.querySelectorAll('#fullDetailTitle img').length`), 0);
    console.log('PASS list/detail: synthetic text rendered without HTML execution');

    stage = 'original file validation';
    await click(`document.querySelector('[data-detail-tab="requirements"]')`);
    await click(button('로컬 원본 대조 실행'));
    await waitFor(() => textIncludes('원본 파일과 추출된 저장 증거를 각각 선택하세요.'), 'missing file message');
    const upload = async file => {
      const {root} = await send('DOM.getDocument');
      const {nodeId} = await send('DOM.querySelector', {nodeId: root.nodeId, selector: '#fullDetailPane input[type=file]'});
      assert(nodeId, 'Missing original file input');
      await send('DOM.setFileInputFiles', {nodeId, files: [file]});
      await click(button('로컬 원본 대조 실행'));
    };
    await upload(fixtureInfo.mismatch);
    await waitFor(() => textIncludes('대조 상태: ORIGINAL_SHA_MISMATCH'), 'mismatched original');
    await upload(fixtureInfo.upload);
    await waitFor(() => textIncludes('대조 상태: REPRODUCED_TEXT'), 'original reproduced');
    console.log('PASS file input: missing/mismatch/reproduced synthetic TXT');

    stage = 'manual history required fields';
    await click(`document.querySelector('[data-detail-tab="decision"]')`);
    await click(button('제출·평가 이력 수동 기록'));
    await waitFor(() => textIncludes('확인 날짜와 근거 자료 설명을 모두 입력하세요.'), 'required fields');
    await evaluate(`(() => {
      const pane=document.querySelector('#fullDetailPane');
      pane.querySelector('input[type=date]').value='2026-10-18';
      pane.querySelector('input[maxlength="160"]').value='P09 합성 제출 확인';
    })()`);
    stage = 'manual save and reload';
    await click(button('제출·평가 이력 수동 기록'));
    await waitFor(() => textIncludes('SUBMITTED / 2026-10-18 / P09 합성 제출 확인'), 'saved history');
    const previousLoad = loads;
    await send('Page.reload', {ignoreCache: true});
    await waitFor(() => loads > previousLoad, 'new document after reload');
    await openDetail();
    await click(`document.querySelector('[data-detail-tab="decision"]')`);
    await waitFor(() => textIncludes('SUBMITTED / 2026-10-18 / P09 합성 제출 확인'), 'persisted history');
    const state = await evaluate(`fetch('/api/dashboard').then(r=>r.json()).then(p=>({
      revision:p.dashboard.revision, final:p.dashboard.notices[0].final,
      events:p.dashboard.notices[0].submission_events, history:p.dashboard.history}))`);
    assert.equal(state.revision, 2); assert.equal(state.final, 'bid'); assert.equal(state.events.length, 1);
    assert.deepEqual(state.history, []);
    assert.equal(state.events[0].source, 'HUMAN_DECLARED_UNVERIFIED');
    console.log('PASS manual history: required fields/save/reload; final decision preserved');
    stage = 'mobile detail';
    await send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: true});
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow');
    assert.deepEqual(errors, []); assert.deepEqual(external, []);
    console.log('PASS 390px detail/no uncaught page exceptions/no external page requests');
  } catch (error) {
    throw Error(`${stage}: ${error.message}`);
  } finally {
    clearTimeout(watchdog);
    if (chrome) {
      if (chrome.exitCode === null) {
        await cdp?.send('Browser.close').catch(() => {});
        await Promise.race([chromeClosed, delay(3000)]);
        if (chrome.exitCode === null) chrome.kill();
      }
      await Promise.race([chromeClosed, delay(3000)]);
    }
    try {
      if (fixture) {
        if (!fixture.stdin.destroyed) fixture.stdin.end('\n');
        await Promise.race([fixtureClosed, delay(5000)]);
        if (fixtureExit === undefined) {
          fixture.kill();
          await Promise.race([fixtureClosed, delay(3000)]);
          throw Error('Fixture cleanup timeout');
        }
        assert.equal(fixtureExit, 0, 'Synthetic fixture failed during cleanup');
        assert(lines.includes('SYNTHETIC_CLEANUP_PASS'), 'Synthetic preservation/cleanup not verified');
      }
    } finally {
      // Delete only the fresh profile owned by this invocation, never an existing Chrome profile.
      assert.equal(path.dirname(profile), path.resolve(os.tmpdir()));
      assert(path.basename(profile).startsWith('p09-chrome-'));
      fs.rmSync(profile, {recursive: true, force: true, maxRetries: 3, retryDelay: 200});
    }
  }
  console.log('PASS CHROME_SYNTHETIC_E2E (not user UI approval or deployment)');
}

main().catch(error => { console.error(`FAIL ${error.message}`); process.exitCode = 1; });
