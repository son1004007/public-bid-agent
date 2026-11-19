// Real Chromium CDP acceptance using a fresh synthetic test profile.
// No ChromeDriver download, user profile, existing service or production data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const {setTimeout: delay} = require('node:timers/promises');

async function main() {
  const [chrome, fixture] = process.argv.slice(2);
  assert(path.isAbsolute(chrome) && fs.statSync(chrome).isFile());
  assert(/^http:\/\/127\.0\.0\.1:\d+$/.test(fixture));
  assert.notEqual(new URL(fixture).port, '8000');
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'bid-workspace-cdp-'));
  const child = spawn(chrome, ['--headless', '--remote-debugging-port=0',
    '--remote-debugging-address=127.0.0.1', '--user-data-dir='+profile,
    '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    '--disable-sync', '--window-size=1280,900', 'about:blank'],
    {windowsHide:true, stdio:'ignore'});
  let ws, closed = false, fatal, sequence = 0, loads = 0, sessionId, stage='startup';
  const pending = new Map();
  const childExit = new Promise(resolve => {
    child.once('exit', resolve);
    child.once('error', () => { fatal = Error('Chrome launch failed'); resolve(); });
  });
  const watchdog = setTimeout(() => { fatal = Error('CDP overall timeout'); child.kill(); ws?.close(); }, 80000);
  function failPending() {
    for (const entry of pending.values()) {
      clearTimeout(entry.timer); entry.reject(Error('CDP connection closed'));
    }
    pending.clear();
  }
  function send(method, params={}, target) {
    if (closed || fatal) return Promise.reject(fatal || Error('CDP closed'));
    return new Promise((resolve,reject) => {
      const id=++sequence;
      const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},8000);
      pending.set(id,{resolve,reject,timer});
      ws.send(JSON.stringify({id,method,params,...(target?{sessionId:target}:{})}));
    });
  }
  async function waitFor(check,label,timeout=12000) {
    const end=Date.now()+timeout;
    while(Date.now()<end) {
      if(fatal) throw fatal;
      if(await check())return;
      await delay(100);
    }
    throw Error(label);
  }
  try {
    const active=path.join(profile,'DevToolsActivePort');
    await waitFor(()=>fs.existsSync(active),'Chrome debugging endpoint unavailable',18000);
    const [port,endpoint]=fs.readFileSync(active,'utf8').trim().split(/\r?\n/);
    assert(/^\d{1,5}$/.test(port) && Number(port)>0 && Number(port)<=65535);
    assert(/^\/devtools\/browser\/[a-f0-9-]+$/i.test(endpoint));
    ws=new WebSocket('ws://127.0.0.1:'+port+endpoint);
    await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(Error('CDP socket open timeout')),8000);
      ws.addEventListener('open',()=>{clearTimeout(timer);resolve();},{once:true});
      ws.addEventListener('error',()=>{clearTimeout(timer);reject(Error('CDP socket error'));},{once:true});
    });
    ws.addEventListener('close',()=>{closed=true;failPending();});
    ws.addEventListener('message',ev=>{
      const msg=JSON.parse(ev.data);
      if(msg.id){
        const e=pending.get(msg.id);if(!e)return;
        pending.delete(msg.id);clearTimeout(e.timer);
        if(msg.error)e.reject(Error('CDP command rejected'));
        else e.resolve(msg.result);
      } else if(msg.sessionId===sessionId) {
        if(msg.method==='Page.loadEventFired')loads++;
        if(msg.method==='Runtime.exceptionThrown')fatal=Error('Uncaught page exception');
        if(msg.method==='Fetch.requestPaused'){
          const {requestId,request}=msg.params;
          const local=new URL(request.url).origin===fixture;
          if(!local)fatal=Error('Unexpected external page request');
          send(local?'Fetch.continueRequest':'Fetch.failRequest',
            local?{requestId}:{requestId,errorReason:'BlockedByClient'},sessionId)
            .catch(()=>{fatal ||= Error('Page interception failed');});
        }
      }
    });
    const version=await send('Browser.getVersion');
    console.log('CDP browser '+version.product);
    const {targetId}=await send('Target.createTarget',{url:'about:blank'});
    ({sessionId}=await send('Target.attachToTarget',{targetId,flatten:true}));
    const cmd=(method,params)=>send(method,params,sessionId);
    await cmd('Page.enable');await cmd('Runtime.enable');
    await cmd('Fetch.enable',{patterns:[{urlPattern:'*'}]});
    const js=async expression=>{
      if(fatal)throw fatal;
      const r=await cmd('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
      assert(!r.exceptionDetails,'Page script failed');
      return r.result.value;
    };
    const visible=id=>"document.getElementById("+JSON.stringify(id)+")&&!document.getElementById("+JSON.stringify(id)+").hidden";
    const wait=(expression,label)=>waitFor(()=>js('Boolean('+expression+')'),label);
    const fill=(id,value)=>js('document.getElementById('+JSON.stringify(id)+').value='+JSON.stringify(value));
    const click=selector=>js('document.querySelector('+JSON.stringify(selector)+').click()');
    const submit=id=>click('#'+id+' button[type=submit]');
    async function navigate(reload=false){
      const before=loads;
      await cmd(reload?'Page.reload':'Page.navigate',reload?{}:{url:fixture+'/workspace'});
      await waitFor(()=>loads>before,'Page load timeout');
    }
    const old='Synthetic!Initial39Blue', next='Changed!Independent74Green';
    const title='<img src=x onerror="alert(1)"> Synthetic notice';
    async function login(password){
      await wait(visible('loginForm'),'Login form not available');
      await fill('username','browser-synthetic');await fill('password',password);await submit('loginForm');
    }
    stage='initial login';await navigate();await login(old);
    await wait(visible('passwordForm'),'Password change required');
    assert(await js("document.getElementById('businessContent').hidden"));
    stage='limited reload';await navigate(true);
    await wait(visible('passwordForm'),'Limited session reload');
    assert(await js("document.getElementById('businessContent').hidden"));
    stage='password change';await fill('currentPassword',old);await fill('newPassword',next);
    await submit('passwordForm');await login(next);
    await wait(visible('businessContent'),'Full session not available');
    await wait("document.querySelector('[data-notice-id]')",'Notice list not rendered');
    assert.equal(await js("document.querySelector('.notice-title-btn').textContent"),title);
    assert.equal(await js("document.querySelectorAll('#noticeTableBody img').length"),0);
    stage='detail';await click('.notice-title-btn');
    await wait("document.querySelector('#dTitle').textContent === "+JSON.stringify(title),'Notice detail unavailable');
    stage='logout';await click('#logoutBtn');
    await wait("document.getElementById('authStatus').textContent === '로그아웃되었습니다.'",'Logout incomplete');
    await wait(visible('loginForm'),'Logout login form');
    await navigate(true);await wait(visible('loginForm'),'Logged out reload');
    assert(await js("document.getElementById('businessContent').hidden"));
    assert.equal(await js("document.getElementById('noticeTableBody').textContent"),'');
    if(fatal)throw fatal;
    console.log('CDP_WORKSPACE_ACCEPTANCE_PASS');
  } catch(error) {
    console.error('CDP_WORKSPACE_FAILED_STAGE='+stage+'; '+error.message);
    process.exitCode=1;
  } finally {
    clearTimeout(watchdog);
    if(ws && !closed && ws.readyState===WebSocket.OPEN) {
      try {await send('Browser.close');} catch {}
      ws.close();
    }
    failPending();
    if(child.exitCode===null && child.signalCode===null) {
      await Promise.race([childExit,delay(3000)]);
      if(child.exitCode===null && child.signalCode===null)child.kill();
    }
    await Promise.race([childExit,delay(3000)]);
    try {fs.rmSync(profile,{recursive:true,force:true,maxRetries:4,retryDelay:250});}
    catch {console.error('CDP_PROFILE_CLEANUP_FAILED');process.exitCode=1;}
  }
}
main().catch(()=>{console.error('CDP_WORKSPACE_PREFLIGHT_FAILED');process.exitCode=1;});
