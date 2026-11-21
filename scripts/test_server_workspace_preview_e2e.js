/**
 * 파일 설계 계약
 * 목적: 독립 합성 HTML의 DEF-01~04, STOP 및 전체 경로를 Playwright page에서 확인한다.
 * 입력/출력: 시안이 열린 page -> 검사 집계. 실제 API/파일/키/운영 자료는 사용하지 않는다.
 * 부작용: 테스트 브라우저의 메모리 입력과 viewport만 변경한다. reload로 초기화한다.
 * 실행: Playwright browser_run_code 도구의 filename으로 이 파일을 지정한다.
 */
async (page) => {
 const results=[],errors=[],requests=[];
 const check=(name,ok)=>results.push({name,ok:!!ok});
 const onError=e=>errors.push(e.message),onRequest=r=>requests.push(r.url());
 page.on('pageerror',onError);page.on('request',onRequest);
 try {
 await page.reload();
 const route=async(r)=>page.evaluate(r=>go(r),r);
 const click=async(mock)=>page.locator('[data-mock="'+mock+'"]').click();
 const read=async(fn)=>page.evaluate(fn);
 const selectScenario=async(value)=>{if(!await page.locator('#proposalScenario').isVisible())await page.getByText('저장 오류 시안',{exact:true}).click();await page.locator('#proposalScenario').selectOption(value);};
 await route('account');
 check('session field removed',await page.locator('#account-timeout').count()===0);
 check('policy readonly unknown',(await page.locator('#main').innerText()).includes('정책 버전: 미연결'));
 await page.locator('#account-display').fill('합성 표시 이름');await page.locator('[data-save="account"]').click();
 check('display save whitelist',await read(()=>adminSaved.account.display==='합성 표시 이름'&&!Object.hasOwn(adminSaved.account,'timeout')));
 await route('proposal');
 check('three sections',await page.locator('[data-proposal][data-property="body"]').count()===3);
 await page.locator('#proposalDraft').fill('첫 절 보존 <img src=x onerror=alert(1)>');
 await click('proposal-save');
 check('one atomic revision',await read(()=>proposalState().head===1&&proposalState().snapshots.length===1&&proposalState().snapshots[0].sections.length===3));
 await click('proposal-save');check('duplicate no revision',await read(()=>proposalState().head===1));
 await selectScenario('invalid');await click('proposal-save');
 check('422 rollback',await read(()=>proposalState().head===1&&proposalState().snapshots.length===1));
 check('422 visible',(await page.locator('#proposalStatus').innerText()).startsWith('422'));
 await selectScenario('oversize');await click('proposal-save');
 check('413 rollback',await read(()=>proposalState().head===1&&proposalState().snapshots.length===1));
 check('413 input kept',(await page.locator('#proposalDraft').inputValue()).startsWith('첫 절 보존'));
 await selectScenario('normal');await page.locator('#proposal-2-title').fill('');await click('proposal-save');
 check('real section validation',(await page.locator('#proposalStatus').innerText()).startsWith('422'));
 await page.locator('#proposal-2-title').fill('일정 수정');await click('proposal-save');
 check('full revision next',await read(()=>proposalState().head===2&&proposalState().snapshots[0].sections[2].title==='인력과 일정'));
 await selectScenario('conflict');await click('proposal-save');
 check('409 preserves local',await read(()=>proposalState().head===3&&proposalState().base===2&&proposalState().draft[2].title==='일정 수정'));
 await click('proposal-rebase');await click('proposal-save');
 check('explicit rebase whole save',await read(()=>proposalState().head===4&&proposalState().snapshots.at(-1).sections.length===3));
 check('XSS escaped',await page.locator('#main img').count()===0);
 for(const format of ['hwpx','docx']){await page.locator('#exportFormat').selectOption(format);await click('export-preview');check(format+' mock adapter',(await page.locator('#exportStatus').innerText()).includes(format.toUpperCase())&&(await page.locator('#exportStatus').innerText()).includes('실제 파일 없음'));}
 await page.evaluate(()=>{selected=2;go('proposal')});
 check('proposal per notice',await read(()=>proposalState().head===0&&!proposalState().draft[0].body.includes('첫 절')));
 await page.evaluate(()=>{selected=1;go('review')});
 check('merged row exists',await page.locator('.structure-table [rowspan="2"]').count()===2);
 check('merged column exists',await page.locator('.structure-table [colspan="2"]').count()===1);
 check('footnote anchor target',await page.locator('#anchor-fn1').getAttribute('href')==='#footnote-fn1'&&await page.locator('#footnote-fn1').count()===1);
 await page.locator('#structureMode').selectOption('UNKNOWN');await page.locator('#checked').check();await page.locator('[data-action="approve"]').click();
 check('unknown cannot approve',await read(()=>approvedReview===null));
 check('unknown visible',(await page.locator('#structureStatus').innerText()).includes('UNKNOWN'));
 await page.locator('#structureMode').selectOption('PARSED');await page.locator('#checked').check();await page.locator('[data-action="approve"]').click();
 check('synthetic approval still works',await read(()=>approvedReview!==null));
 await page.locator('#gold').fill('수정된 합성 구절');check('edit invalidates approval',await read(()=>approvedReview===null));
 await route('decisions');await page.locator('#finalReason').fill('합성 결정 사유');await page.locator('#finalChoice').selectOption('참여 결정');await page.locator('#finalChecked').check();
 await click('source-change');await page.locator('[data-admin="final-decision"]').click();
 check('source changed blocks commit',await read(()=>!finalDecisions[1]&&decisionState().conflict));
 check('reason preserved',await page.locator('#finalReason').inputValue()==='합성 결정 사유');
 check('confirm reset',!await page.locator('#finalChecked').isChecked()&&await page.locator('[data-admin="final-decision"]').isDisabled());
 await click('decision-diff');check('diff visible',await page.locator('.diffgrid section').count()===2);
 await click('decision-refresh');await page.locator('[data-admin="final-decision"]').click();
 check('new snapshot needs confirmation',await read(()=>!finalDecisions[1]));
 await page.locator('#finalChecked').check();await page.locator('[data-admin="final-decision"]').click();
 check('new snapshot final',await read(()=>finalDecisions[1]?.snapshot===sourceStamp()));
 await click('source-change');await page.locator('[data-admin="final-decision"]').click();await click('decision-diff');await click('source-change');await click('decision-refresh');
 check('repeat changes take latest snapshot',await read(()=>decisionState().snapshot===sourceStamp()&&!decisionState().checked));
 await route('proposal');await page.locator('#proposalDraft').fill('추가 수동 수정');await click('proposal-save');await route('decisions');await page.locator('[data-admin="final-decision"]').click();
 check('proposal revision conflicts',await read(()=>decisionState().conflict));
 await page.evaluate(()=>{selected=2;go('decisions')});check('decision drafts scoped',await page.locator('#finalReason').inputValue()==='');
 await page.evaluate(()=>{selected=5;go('decisions')});check('cancelled participation disabled',await page.locator('#finalChoice option').nth(1).isDisabled());
 await page.evaluate(()=>{selected=1;go('jobs')});
 await page.locator('[data-job="2"][data-job-action="retry"]').click();
 await page.locator('[data-job="2"][data-job-action="finish"]').click();
 check('ordinary model failure STOP',await read(()=>workflowState().state==='STOPPED'&&workflowState().jobs[2].state==='FAILED'));
 check('ordinary failure dependent blocked',await read(()=>workflowState().jobs[3].state==='REVIEW_REQUIRED'));
 check('ordinary failure cannot retry directly',await page.locator('[data-job="2"][data-job-action="retry"]').isDisabled());
 await click('stop-error');
 check('STOP states',await read(()=>workflowState().state==='STOPPED'&&workflowState().jobs[2].state==='FAILED'&&workflowState().jobs[3].state==='REVIEW_REQUIRED'));
 check('STOP retry disabled',await page.locator('[data-job="2"][data-job-action="retry"]').isDisabled());
 const version=await read(()=>proposalState().head);await page.waitForTimeout(120);
 check('no auto draft after STOP',await read(()=>proposalState().head)===version);
 await route('operations');check('operations STOP visible',(await page.locator('.stop-panel').innerText()).includes('STOPPED'));
 await click('stop-timeout');check('unknown resume disabled',await page.locator('[data-mock="workflow-resume"]').isDisabled());
 check('unknown confirmation disabled',await page.locator('#resumeConfirmed').isDisabled());
 await route('proposal');await click('export-preview');check('STOP export blocked',(await page.locator('#exportStatus').innerText()).startsWith('STOP'));
 check('saved version kept',await read(()=>proposalState().head)===version);
 await route('jobs');await click('resolve-result');check('resolved remains stopped',await read(()=>workflowState().state==='STOPPED'));
 await page.locator('#resumeConfirmed').check();await click('workflow-resume');
 check('explicit resume only queues',await read(()=>workflowState().state==='ACTIVE'&&workflowState().jobs[2].state==='QUEUED'));
 await page.evaluate(()=>{selected=2;go('jobs')});check('independent notice unaffected',await read(()=>workflowState().state==='ACTIVE'));
 // Existing interactions remain available.
 await route('notices');await page.locator('#scenario').selectOption('slow');await page.waitForTimeout(3100);check('3s loading hint',await page.locator('#slowHint').isVisible());
 await page.locator('[data-action="stop-loading"]').click();check('loading stop cleanup',await read(()=>!loadingActive&&loadingTimers.length===0));
 await route('criteria');await page.locator('#criteria-w0').fill('20');await page.locator('[data-save="criteria"]').click();check('weight validation kept',(await page.locator('#saveStatus').innerText()).includes('합계'));
 for(const width of [390,1440]){
  await page.setViewportSize({width,height:950});
  for(const r of await read(()=>Object.keys(names))){await route(r);check(width+' '+r+' heading',await page.locator('h1').count()===1);check(width+' '+r+' no overflow',await read(()=>document.documentElement.scrollWidth<=innerWidth));check(width+' '+r+' no middle dot',!(await page.locator('body').innerText()).includes('·'));}
  await page.evaluate(()=>{selected=1;go('decisions')});check(width+' conflict panel fit',await read(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 check('no JS errors',errors.length===0);
 check('no external request',requests.every(u=>u.startsWith('http://127.0.0.1:8766/')));
 await page.evaluate(()=>go('screens'));
 return {passed:results.filter(r=>r.ok).length,failed:results.filter(r=>!r.ok),jsErrors:errors};
 } finally {page.off('pageerror',onError);page.off('request',onRequest);}
}
