// Test the committed live workspace script with synthetic DOM/fetch only.
// This does not certify browser, real PostgreSQL, or operational acceptance.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../frontend/public/server-workspace-live.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function setup(handler) {
  const elements = new Map(), calls = [];
  const get = id => {
    if (!elements.has(id)) elements.set(id, {
      textContent:'', innerHTML:'', hidden:false, value:'', disabled:false,
      classList:{add(){},remove(){}}, style:{}, addEventListener(){},
      removeAttribute(key){delete this[key];},
      replaceChildren(){this.innerHTML='';this.textContent='';}
    });
    return elements.get(id);
  };
  const ctx = vm.createContext({
    document:{getElementById:get,querySelectorAll:()=>[]},
    window:{addEventListener(){}}, URL, URLSearchParams, console,
    fetch:async (url, options)=>{calls.push({url,options});return handler(url,options);}
  });
  vm.runInContext(script,ctx);
  return {get,calls,run:code=>vm.runInContext(code,ctx)};
}
const response = (status,data) => ({status,ok:status>=200&&status<300,json:async()=>data});
const full = {access:'FULL',auth_epoch:2,user:{display_name:'Synthetic user'}};
const id = 'a1111111-1111-4111-8111-111111111111';
const hostile = '<img src=x onerror="alert(1)">';

test('anonymous workspace never auto-posts credentials or reads business data',async()=>{
  const x=setup(()=>response(401,{}));
  await x.run('initAuth()');
  assert.deepEqual(x.calls.map(c=>c.url),['/api/v1/auth/session']);
  assert.equal(x.get('businessContent').hidden,true);
  assert.equal(x.get('loginForm').hidden,false);
});

test('limited session can see password form but does not query business endpoints',async()=>{
  const x=setup(()=>response(200,{data:{...full,access:'PASSWORD_CHANGE_REQUIRED'}}));
  await x.run('initAuth()');
  assert.equal(x.calls.length,1);
  assert.equal(x.get('passwordForm').hidden,false);
  assert.equal(x.get('businessContent').hidden,true);
});

test('external source and notice fields are not executable HTML or invented URLs',async()=>{
  const x=setup(url=>{
    if(url.includes('?')) return response(200,{data:[{id,title:hostile,buyer:hostile,notice_number:hostile,categories:[hostile]}],page:{total:1,next_cursor:null}});
    return response(200,{data:{id,title:hostile,source_url:'javascript:alert(1)',categories:[hostile],documents:[{logical_key:hostile,versions:[{media_type:hostile,source_url:'https://g2b.go.kr/?secret=fixture'}]}]}});
  });
  x.run('showSession('+JSON.stringify(full)+')');
  await x.run('loadNotices()');
  assert.ok(x.get('noticeTableBody').innerHTML.includes('&lt;img'));
  assert.ok(!x.get('noticeTableBody').innerHTML.includes('<img'));
  await x.run('openNoticeDetail('+JSON.stringify(id)+')');
  assert.equal(x.get('dTitle').textContent,hostile);
  assert.equal(x.get('dG2bLink').hidden,true);
  assert.ok(!x.get('dDocuments').innerHTML.includes('<img'));
  assert.ok(!x.get('dDocuments').innerHTML.includes('secret=fixture'));
  assert.equal(x.run("allowedSourceUrl('https://g2b.go.kr.example.invalid/x')"),'');
  assert.equal(x.run("allowedSourceUrl('https://g2b.go.kr/public')"),'https://g2b.go.kr/public');
});

test('session expiry clears all visible data and invalidates pending responses',async()=>{
  let resolve;
  const pending=new Promise(r=>{resolve=r;});
  const x=setup(()=>pending);
  x.run('showSession('+JSON.stringify(full)+')');
  const loading=x.run('loadNotices()');
  x.run("showSession(null,'expired')");
  resolve(response(200,{data:[{id,title:'stale private fixture'}]}));
  await loading;
  assert.equal(x.get('businessContent').hidden,true);
  assert.equal(x.get('noticeTableBody').innerHTML,'');
  const y=setup(()=>response(401,{}));
  y.run('showSession('+JSON.stringify(full)+')');
  await y.run('loadNotices()');
  assert.equal(y.get('businessContent').hidden,true);
  assert.equal(y.get('loginForm').hidden,false);
});
