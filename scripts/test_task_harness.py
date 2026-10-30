"""H01 실행/증거 실패 주입 인수. 합성 임시 Git 저장소와 전용 실행 폴더만 사용."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import task_harness as h
from harness_core.process import execute


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base/'repo'; self.repo.mkdir()
        for name in h.TRUSTED:
            dest=self.repo/name; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(h.ROOT/name,dest)
        task=json.loads((h.ROOT/'harness/tasks/A01.json').read_text())
        task.update(task_id='SMOKE',required_checks=['smoke','full'],selected_checks=['smoke'],allowed_changes=['fixture/'])
        dest=self.repo/'harness/tasks/SMOKE.json'; dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(task))
        registry={'schema_version':1,'commands':{'smoke':{'tests':['test_sample.Sample.test_ok'],'import_dir':'fixture','timeout_seconds':2,'output_limit_bytes':4096}}}
        # Registry is a trusted policy, but code matching is independently enforced.
        self.registry=registry
        (self.repo/'harness/commands.json').write_text(json.dumps(registry))
        (self.repo/'fixture').mkdir()
        self.fixture=self.repo/'fixture/test_sample.py'
        self.fixture.write_text('import unittest\nclass Sample(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
        self.g('init','-q'); self.g('config','core.autocrlf','false'); self.g('config','user.email','fixture@example.invalid'); self.g('config','user.name','fixture')
        self.g('add','.'); self.g('commit','-qm','fixture')
        self.sha=self.g('rev-parse','HEAD').strip()

    def g(self,*args):
        return subprocess.check_output(['git','-C',str(self.repo),*args],text=True)

    def run_fixture(self, code=None):
        if code is not None:
            self.fixture.write_text(code)
            self.g('add','.');self.g('commit','-qm','candidate')
        candidate=self.g('rev-parse','HEAD').strip()
        result=h.run(self.repo,self.sha,candidate,'SMOKE',self.base/'run')
        return result

    def test_success_not_task_done(self):
        result=self.run_fixture()
        self.assertEqual(result['state'],'LOCAL_VERIFIED');self.assertFalse(result['task_complete'])
        self.assertEqual(result['missing_checks'],['full'])
        self.assertEqual(h.verify(self.base/'run'),result)

    def test_real_failure(self):
        r=self.run_fixture('import unittest\nclass Sample(unittest.TestCase):\n def test_ok(self): self.fail("negative canary")\n')
        self.assertEqual(r['state'],'VERIFY_FAILED')

    def test_skip_rejected(self):
        r=self.run_fixture('import unittest\nclass Sample(unittest.TestCase):\n @unittest.skip("canary")\n def test_ok(self): pass\n')
        self.assertEqual(r['state'],'VERIFY_FAILED')

    def test_timeout_descendant(self):
        code='import unittest,subprocess,sys,time\nclass Sample(unittest.TestCase):\n def test_ok(self):\n  subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"])\n  time.sleep(60)\n'
        r=self.run_fixture(code)
        self.assertEqual(r['state'],'TIMED_OUT')
        data=h.read_json(self.base/'run/run.json')
        self.assertTrue(data['checks'][0]['outcome']['cleanup'])

    def test_output_cap(self):
        r=self.run_fixture('import unittest\nclass Sample(unittest.TestCase):\n def test_ok(self):\n  print("x"*200000)\n')
        self.assertEqual(r['state'],'VERIFY_FAILED')
        self.assertLessEqual((self.base/'run/smoke/stdout.log').stat().st_size,4096)

    def test_snapshot_tamper(self):
        self.run_fixture(); (self.base/'run/snapshot/fixture/test_sample.py').write_text('changed')
        self.assertEqual(h.verify(self.base/'run')['state'],'STALE')

    def test_report_missing_or_tampered(self):
        self.run_fixture(); p=self.base/'run/smoke/report.json'
        p.write_text('{}');self.assertEqual(h.verify(self.base/'run')['state'],'EVIDENCE_INVALID')
        p.unlink();self.assertEqual(h.verify(self.base/'run')['state'],'EVIDENCE_INVALID')

    def test_summary_tamper(self):
        self.run_fixture(); p=self.base/'run/run.json';d=h.read_json(p);d['checks'][0]['outcome']['exit_code']=42;h.write_json(p,d)
        self.assertEqual(h.verify(self.base/'run')['state'],'EVIDENCE_INVALID')

    def test_event_tamper(self):
        self.run_fixture(); (self.base/'run/events.jsonl').write_text('{}')
        self.assertEqual(h.verify(self.base/'run')['state'],'EVIDENCE_INVALID')

    def test_existing_run_never_overwritten(self):
        self.run_fixture()
        with self.assertRaises(FileExistsError):self.run_fixture()

    def test_changed_scope(self):
        (self.repo/'README.md').write_text('outside fixture scope')
        self.g('add','.');self.g('commit','-qm','outside')
        with self.assertRaisesRegex(h.Invalid,'scope'):h.validate(self.repo,self.sha,self.g('rev-parse','HEAD').strip(),'SMOKE')

    def test_unknown_command(self):
        task=json.loads((self.repo/'harness/tasks/SMOKE.json').read_text());task['selected_checks']=['missing'];task['required_checks']=['missing']
        (self.repo/'harness/tasks/SMOKE.json').write_text(json.dumps(task));self.g('add','.');self.g('commit','-qm','bad task')
        with self.assertRaisesRegex(h.Invalid,'unknown command'):h.policy(self.repo,self.g('rev-parse','HEAD').strip(),'SMOKE')

    def test_mutable_ref_rejected(self):
        with self.assertRaises(h.Invalid):h.commit(self.repo,'HEAD')

    def test_path_alias_rejected(self):
        for name in ('../x','/x','C:/x','a\\b','a./b','CON.txt','x/../y'):
            with self.subTest(name=name),self.assertRaises(h.Invalid):h.safe_path(name)

    def test_report_identity_count_and_exit(self):
        context=dict(run_id='r',check_id='c',source_digest='s',adapter_digest='a')
        report=dict(context,tests_run=1,test_ids=['t.C.test_a'],failures=0,errors=0,skipped=0,expected_failures=0,unexpected_successes=0)
        definition={'tests':['t.C.test_a']};outcome={'exit_code':0}
        self.assertEqual(h.report_state(report,context,definition,outcome),'LOCAL_VERIFIED')
        for key,value in [('run_id','other'),('check_id','other'),('test_ids',['other']),('tests_run',True)]:
            bad=dict(report,**{key:value});self.assertEqual(h.report_state(bad,context,definition,outcome),'EVIDENCE_INVALID')
        self.assertEqual(h.report_state(dict(report,tests_run=0),context,definition,outcome),'VERIFY_FAILED')
        self.assertEqual(h.report_state(report,context,definition,{'exit_code':1}),'VERIFY_FAILED')


if __name__=='__main__':unittest.main()
