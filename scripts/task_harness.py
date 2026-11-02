"""H01 합성 개발 검증 하네스.
입력: 명시적으로 신뢰한 불변 Git SHA의 정책/실행기와 후보 Git SHA.
출력: 전용 폴더의 snapshot, 구조화 보고서, hash 결속 실행 기록.
기준 코드와 현재 실행기 일치 검사 후 허용 unittest만 실행한다. 운영 자료 접근 없음.
실패는 성공으로 승격하지 않는다. 외부 GO/CI/사람 검수·resume는 미구현이다.
같은 사용자 권한의 악의적인 전체 증거 재작성/비신뢰 코드 격리는 보장하지 않는다.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
TRUSTED = ('scripts/task_harness.py', 'scripts/harness_core/__init__.py', 'scripts/harness_core/adapter.py', 'scripts/harness_core/process.py')
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


class Invalid(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, limit=262144):
    data = Path(path).read_bytes()
    if len(data) > limit:
        raise Invalid('oversize JSON')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise Invalid('duplicate JSON key')
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=unique)


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_bytes(canonical(value))
    os.replace(temp, path)


def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or value.startswith('/'):
        raise Invalid('invalid relative path')
    parts = value.rstrip('/').split('/')
    for part in parts:
        if part in ('', '.', '..') or part.endswith(('.', ' ')) or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
            raise Invalid('unsafe path component')
    return value


def no_links(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise Invalid('symlink/reparse path')
    return path


def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=30)
    if p.returncode:
        raise Invalid('Git operation failed')
    return p.stdout


def commit(repo, ref):
    if not re.fullmatch('[0-9a-f]{40}', ref):
        raise Invalid('full immutable commit SHA required')
    actual = git(repo, 'rev-parse', ref + '^{commit}').decode().strip()
    if actual != ref:
        raise Invalid('commit mismatch')
    return ref


def blob(repo, sha, path):
    value = git(repo, 'show', sha + ':' + safe_path(path))
    if len(value) > MAX_FILE:
        raise Invalid('source file too large')
    return value


def tree(repo, sha):
    result = {}; aliases = set(); total = 0
    for item in git(repo, 'ls-tree', '-rz', sha).split(b'\0'):
        if not item:
            continue
        meta, raw = item.split(b'\t', 1)
        mode, kind, _ = meta.decode().split()
        path = safe_path(raw.decode('utf-8'))
        if mode not in ('100644', '100755') or kind != 'blob' or path.casefold() in aliases:
            raise Invalid('unsafe tree entry')
        aliases.add(path.casefold())
        data = blob(repo, sha, path)
        total += len(data)
        if total > MAX_TOTAL:
            raise Invalid('source tree too large')
        result[path] = (mode, data)
    return result


def manifest(files):
    return {k: {'mode': v[0], 'sha256': digest(v[1])} for k,v in sorted(files.items())}


def snapshot_files(directory):
    result = {}
    for path in sorted(Path(directory).rglob('*')):
        no_links(path)
        if path.is_file():
            rel = path.relative_to(directory).as_posix()
            data = path.read_bytes()
            if len(data) > MAX_FILE:
                raise Invalid('snapshot file too large')
            result[rel] = digest(data)
    return result


def matches(path, prefixes):
    return any(path.casefold() == p.casefold() or (p.endswith('/') and path.casefold().startswith(p.casefold())) for p in prefixes)


def policy(repo, sha, task_id):
    if not re.fullmatch('[A-Z][A-Z0-9_-]{1,30}', task_id):
        raise Invalid('task ID')
    registry = json.loads(blob(repo, sha, 'harness/commands.json'))
    task = json.loads(blob(repo, sha, 'harness/tasks/' + task_id + '.json'))
    fields = {'schema_version','task_id','mode','depends_on','required_checks','selected_checks','allowed_changes','forbidden_changes','requires_independent_review','requires_ci','requires_human_evidence','max_attempts'}
    if set(task) != fields or type(task['schema_version']) is not int or task['schema_version'] != 1 or task['task_id'] != task_id or task['mode'] != 'synthetic':
        raise Invalid('task schema')
    if task['depends_on'] != []:
        raise Invalid('H01 dependencies unsupported; BLOCKED_DEPENDENCY')
    if type(task['max_attempts']) is not int or task['max_attempts'] != 1:
        raise Invalid('H01 permits one manual attempt per new run')
    for key in ('requires_independent_review','requires_ci','requires_human_evidence'):
        if type(task[key]) is not bool:
            raise Invalid('gate type')
    for key in ('required_checks','selected_checks','allowed_changes','forbidden_changes'):
        value = task[key]
        if not isinstance(value, list) or any(not isinstance(x,str) for x in value) or len(set(value)) != len(value):
            raise Invalid('task list')
    if not task['selected_checks'] or not set(task['selected_checks']) <= set(task['required_checks']):
        raise Invalid('required check mismatch')
    for value in task['allowed_changes'] + task['forbidden_changes']:
        safe_path(value)
    if set(registry) != {'schema_version','commands'} or registry['schema_version'] != 1:
        raise Invalid('registry schema')
    for key, value in registry['commands'].items():
        if not re.fullmatch('[a-z][a-z0-9_]{0,60}', key):
            raise Invalid('command ID')
        if set(value) != {'tests','import_dir','timeout_seconds','output_limit_bytes'}:
            raise Invalid('command schema')
        if not value['tests'] or len(set(value['tests'])) != len(value['tests']) or any(not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,}', x) for x in value['tests']):
            raise Invalid('test selector')
        safe_path(value['import_dir'])
        for field, lo, hi in [('timeout_seconds',1,120),('output_limit_bytes',1024,1048576)]:
            if type(value[field]) is not int or not lo <= value[field] <= hi:
                raise Invalid('command bound')
    if not set(task['selected_checks']) <= registry['commands'].keys():
        raise Invalid('unknown command')
    return task, registry


def validate(repo, trusted, candidate, task_id):
    if sys.version_info[:2] != (3,12):
        raise Invalid('Python 3.12 required')
    commit(repo, trusted); commit(repo, candidate)
    for path in TRUSTED:
        no_links(ROOT / path)
        if (ROOT / path).read_bytes() != blob(repo, trusted, path):
            raise Invalid('running harness differs from trusted ref')
    task, registry = policy(repo, trusted, task_id)
    base = tree(repo, trusted); files = tree(repo, candidate)
    changed = [p for p in base.keys() | files.keys() if base.get(p) != files.get(p)]
    for path in changed:
        if matches(path, task['forbidden_changes']) or not matches(path, task['allowed_changes']):
            raise Invalid('candidate scope violation: ' + path)
    return task, registry, files


def report_state(report, context, definition, outcome):
    keys = {'run_id','check_id','source_digest','adapter_digest','tests_run','test_ids','failures','errors','skipped','expected_failures','unexpected_successes'}
    if set(report) != keys or any(report[k] != context[k] for k in ('run_id','check_id','source_digest','adapter_digest')):
        return 'EVIDENCE_INVALID'
    counts = ('tests_run','failures','errors','skipped','expected_failures','unexpected_successes')
    if any(type(report[k]) is not int or report[k] < 0 for k in counts):
        return 'EVIDENCE_INVALID'
    if report['tests_run'] == 0:
        return 'VERIFY_FAILED'
    if report['test_ids'] != definition['tests'] or report['tests_run'] != len(definition['tests']):
        return 'EVIDENCE_INVALID'
    if any(report[k] for k in counts[1:]) or outcome['exit_code'] != 0:
        return 'VERIFY_FAILED'
    return 'LOCAL_VERIFIED'


def verify(run_dir, require_event=True):
    folder = no_links(run_dir)
    try:
        data = read_json(folder / 'run.json')
        seal = read_json(folder / 'manifest.json')
        if require_event:
            event_bytes=(folder/'events.jsonl').read_bytes()
            if digest(event_bytes) != seal['event_digest']:
                return {'state':'EVIDENCE_INVALID'}
            event=json.loads(event_bytes)
            saved=event.pop('digest')
            if saved != digest(canonical(event)) or event['sequence'] != 1 or event['previous'] is not None or event['run_id'] != data['run_id']:
                return {'state':'EVIDENCE_INVALID'}
        if digest(canonical(data)) != seal['run_digest']:
            return {'state':'EVIDENCE_INVALID'}
        for name, expected in seal['artifacts'].items():
            safe_path(name); path = no_links(folder / name)
            if digest(path.read_bytes()) != expected:
                return {'state':'EVIDENCE_INVALID'}
        if snapshot_files(folder/'snapshot') != data['source_files']:
            return {'state':'STALE'}
        states = []
        for check in data['checks']:
            outcome = check['outcome']
            if not outcome['cleanup']:
                state = 'BLOCKED_ENVIRONMENT'
            elif outcome['timed_out']:
                state = 'TIMED_OUT'
            elif outcome['output_exceeded']:
                state = 'VERIFY_FAILED'
            else:
                report = read_json(folder / check['report'])
                state = report_state(report, check['context'], check['definition'], outcome)
            states.append(state)
        if len(states) != len(data['task']['selected_checks']) or not states:
            return {'state':'EVIDENCE_INVALID'}
        state = next((x for x in states if x != 'LOCAL_VERIFIED'), 'LOCAL_VERIFIED')
        missing = sorted(set(data['task']['required_checks']) - {x['check_id'] for x in data['checks']})
        gates = ['WAITING_REVIEW', 'WAITING_CI']
        if data['task']['requires_human_evidence']:
            gates.append('WAITING_HUMAN')
        return {'state':state,'run_id':data['run_id'],'checks':states,'missing_checks':missing,
                'external_gates':gates,'task_complete':False}
    except (OSError, ValueError, KeyError, TypeError):
        return {'state':'EVIDENCE_INVALID'}


def run(repo, trusted, candidate, task_id, run_dir):
    task, registry, files = validate(repo, trusted, candidate, task_id)
    folder = no_links(run_dir)
    if not Path(run_dir).is_absolute() or folder == ROOT or ROOT in folder.parents:
        raise Invalid('fresh absolute run directory outside source required')
    folder.mkdir()  # exclusive claim; never reuse/overwrite previous evidence
    snap = folder/'snapshot'; snap.mkdir()
    for name, (_, content) in files.items():
        path = snap/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    source_files = snapshot_files(snap)
    source_digest = digest(canonical(manifest(files)))
    trusted_dir = folder/'trusted'; trusted_dir.mkdir()
    adapter = trusted_dir/'adapter.py'; adapter.write_bytes(blob(repo,trusted,'scripts/harness_core/adapter.py'))
    adapter_digest = digest(adapter.read_bytes())
    data = dict(schema_version=1,run_id=str(uuid.uuid4()),task_id=task_id,task=task,
                trusted_commit=trusted,candidate_commit=candidate,source_digest=source_digest,
                source_files=source_files,task_digest=digest(canonical(task)),registry_digest=digest(canonical(registry)),
                harness_digest=digest(b''.join(blob(repo,trusted,p) for p in TRUSTED)),
                started=stamp(),python=sys.version,platform=sys.platform,checks=[])
    from harness_core.process import execute
    for check_id in task['selected_checks']:
        definition = registry['commands'][check_id]
        check_dir = folder/check_id; check_dir.mkdir()
        report = check_dir/'report.json'
        context = dict(run_id=data['run_id'],check_id=check_id,source_digest=source_digest,adapter_digest=adapter_digest)
        config = dict(context,snapshot=str(snap),report=str(report),tests=definition['tests'],import_dir=definition['import_dir'])
        config_path = check_dir/'input.json'; write_json(config_path,config)
        env = {k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH')}
        temp = check_dir/'temp'; temp.mkdir()
        env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8',TEMP=str(temp),TMP=str(temp),PUBLIC_BID_LOCAL_DATA=str(check_dir/'synthetic'))
        argv = [sys.executable,'-I','-B',str(adapter),str(config_path)]
        start = stamp()
        try:
            outcome = execute(argv,check_dir,env,definition['timeout_seconds'],definition['output_limit_bytes'],check_dir)
        except OSError:
            outcome = dict(exit_code=None,timed_out=False,output_exceeded=False,cleanup=False)
        data['checks'].append(dict(check_id=check_id,definition=definition,context=context,outcome=outcome,
                                   argv=argv,started=start,finished=stamp(),report=report.relative_to(folder).as_posix()))
    data['finished'] = stamp(); write_json(folder/'run.json',data)
    artifacts = {'trusted/adapter.py':digest(adapter.read_bytes())}
    for check in data['checks']:
        for filename in ('report.json','stdout.log','stderr.log','input.json'):
            rel = check['check_id']+'/'+filename; path=folder/rel
            if path.exists():
                if path.stat().st_size > 1048576:
                    raise Invalid('artifact too large')
                artifacts[rel]=digest(path.read_bytes())
    write_json(folder/'manifest.json',dict(run_digest=digest(canonical(data)),artifacts=artifacts))
    result = verify(folder, require_event=False)
    event = dict(sequence=1,previous=None,run_id=data['run_id'],result=result)
    event['digest']=digest(canonical(event))
    event_bytes=canonical(event)+b'\n'
    (folder/'events.jsonl').write_bytes(event_bytes)
    write_json(folder/'manifest.json',dict(run_digest=digest(canonical(data)),artifacts=artifacts,event_digest=digest(event_bytes)))
    return verify(folder)


def main():
    parser=argparse.ArgumentParser(description='H01 synthetic harness; no automatic task DONE')
    subs=parser.add_subparsers(dest='command',required=True)
    for action in ('validate','run'):
        p=subs.add_parser(action); p.add_argument('--task',required=True); p.add_argument('--trusted-ref',required=True)
        p.add_argument('--candidate-ref'); p.add_argument('--repo',default=str(ROOT))
        if action=='run': p.add_argument('--run-dir',required=True)
    for action in ('verify','status','resume'):
        subs.add_parser(action).add_argument('--run-dir',required=True)
    a=parser.parse_args()
    try:
        if a.command=='resume': result={'state':'UNSUPPORTED','reason':'H03 not implemented'}
        elif a.command in ('verify','status'): result=verify(a.run_dir)
        elif a.command=='validate':
            validate(a.repo,a.trusted_ref,a.candidate_ref or a.trusted_ref,a.task)
            result={'state':'VALIDATED','task_complete':False}
        else: result=run(a.repo,a.trusted_ref,a.candidate_ref or a.trusted_ref,a.task,a.run_dir)
    except (Invalid,OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as e:
        result={'state':'INVALID_TASK','reason':str(e)}
    print(json.dumps(result,ensure_ascii=True,sort_keys=True))
    return 0 if result['state'] in ('VALIDATED','LOCAL_VERIFIED') else 1


if __name__=='__main__': sys.exit(main())
