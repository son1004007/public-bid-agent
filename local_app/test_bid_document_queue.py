"""BID-05 합성 계약: 원문/회사 자료 미노출·버전/해시·불변·상한·실패 단계 검증."""
import copy
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bid_document_queue as queue
from bid_now_audit_cli import AuditBlocked
from procurement_filter import KST
from rfp_batch import analyze
from rfp_fulltext import store

AT = datetime(2026, 10, 19, 16, tzinfo=KST)
RAW = 'PRIVATE_BID05_DOCUMENT_AND_COMPANY_CANARY'


def notice(number='BID05SYNTH', hours=12):
    return {'id': 'G2B-'+number+'-001', 'bid_no': number, 'bid_order': '001',
            'source': 'G2B_OFFICIAL_API', 'source_url': 'https://www.g2b.go.kr/',
            'notice_lifecycle': 'CURRENT', 'notice_kind': '일반공고',
            'end': (AT+timedelta(hours=hours)).isoformat(),
            'qualification_deadline': (AT+timedelta(hours=hours-1)).isoformat(),
            'attachments': [{'name': 'synthetic.txt', 'url': 'https://www.g2b.go.kr/synthetic'}],
            'document_status': 'PENDING', 'document_evidence': [], 'final': 'no_bid',
            'finalReason': RAW, 'department_status': 'OUT_OF_SCOPE', 'department_categories': []}


def extracted(root, n=None, truncated=False, warning=False):
    n = n or notice()
    digest = hashlib.sha256(b'SYNTHETIC_ORIGINAL').hexdigest()
    meta = store(root, digest, {'text': RAW, 'characters': len(RAW)+(5 if truncated else 0), 'truncated': truncated})
    item = n['attachments'][0]
    proof = {'status': 'EXTRACTED', 'identity': hashlib.sha256((item['url']+'\n'+item['name']).encode()).hexdigest(),
             'name': item['name'], 'sha256': digest, 'notice_id': n['id'],
             'notice_bid_no': n['bid_no'], 'notice_bid_order': n['bid_order'],
             'warnings': ['PRIVATE_WARNING'] if warning else [], **meta}
    n.update(document_status='EXTRACTED', rfp_text=RAW, document_evidence=[proof])
    return n


def board(root, notices):
    (root/'dashboard.json').write_text(json.dumps({'schema_version': 1, 'revision': 0, 'notices': notices}), encoding='utf-8')


class QueueTests(unittest.TestCase):
    def test_no_attachment_pending_and_unknown_failure_preserve_capability_opportunity(self):
        pending = notice('BID05PENDING'); missing = notice('BID05MISSING'); missing['attachments'] = []
        failed = notice('BID05FAILED'); failed['document_status'] = 'FAILED'
        data = [pending, missing, failed]; before = copy.deepcopy(data)
        result = queue.build(data, at=AT)
        self.assertEqual(result['action_required_count'], 3)
        reasons = {r['id']: r['reason_codes'] for r in result['results']}
        self.assertIn('DOWNLOAD_PENDING', reasons[pending['id']])
        self.assertNotIn('PARTIAL_EXTRACTION', reasons[pending['id']])
        self.assertIn('OFFICIAL_ATTACHMENT_MISSING', reasons[missing['id']])
        self.assertIn('FAILED_STAGE_UNKNOWN', reasons[failed['id']])
        self.assertNotIn('DOWNLOAD_FAILED', reasons[failed['id']])
        self.assertEqual(data, before); self.assertNotIn(RAW, json.dumps(result))
        self.assertFalse(result['automatic_download']); self.assertFalse(result['analysis_complete'])

    def test_cancellation_superseded_stale_closed_and_unknown_deadline(self):
        items = []
        for index, change in enumerate(({'notice_kind': '취소공고'}, {'notice_lifecycle': 'SUPERSEDED'},
                {'rfp_review_status': 'STALE'}, {'end': AT.isoformat()}, {'end': 'unknown'})):
            n = notice('BID05RISK'+str(index)); n.update(change); items.append(n)
        result = queue.build(items, at=AT)
        self.assertEqual(result['held_count'], 4)
        self.assertEqual(result['action_required_count'], 1)
        codes = {c for r in result['held_results'] for c in r['reason_codes']}
        self.assertTrue({'CANCELLED','SUPERSEDED','STALE_SOURCE','DEADLINE_PASSED'} <= codes)
        self.assertTrue(all(r['reevaluation_status']=='BLOCKED_SOURCE' for r in result['held_results']))
        cancelled=notice('BID05CANCELLED');cancelled['notice_lifecycle']='CANCELLED'
        self.assertNotIn('LIFECYCLE_UNVERIFIED',queue.build([cancelled],at=AT)['held_results'][0]['reason_codes'])

    def test_deadline_and_effort_priority_are_deterministic_without_profit(self):
        later = notice('BID05LATER', 80); urgent = notice('BID05URGENT', 2)
        cheap = notice('BID05CHEAP', 2); cheap['attachments'] = []
        result = queue.build([later, urgent, cheap], at=AT)
        self.assertEqual([r['id'] for r in result['results']], [cheap['id'], urgent['id'], later['id']])
        self.assertEqual(result['results'][0]['priority'], 'P1')
        self.assertTrue(all(r['estimated_profit']=='UNVERIFIED' for r in result['results']))

    def test_numeric_revision_alias_duplicate_and_invalid_identity_are_held(self):
        first = notice(); newer = notice(); newer.update(id='G2B-BID05SYNTH-002', bid_order='002')
        alias = copy.deepcopy(newer); alias.update(id='G2B-BID05SYNTH-2', bid_order='2')
        result = queue.build([first, newer, alias, copy.deepcopy(first), {'id': RAW}, None], at=AT)
        self.assertEqual(result['held_count'], 6)
        self.assertNotIn(RAW, json.dumps(result)); self.assertEqual(result['reason_counts']['INVALID_IDENTITY'],2)

    def test_hash_bound_cache_is_stored_text_only_and_source_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); n = extracted(root); board(root, [n])
            before = {p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            report = queue.read_queue(root, at=AT); row = report['results'][0]
            self.assertEqual(row['source_binding'],'STORED_HASHES_MATCH')
            self.assertEqual(row['reevaluation_status'],'STORED_TEXT_ONLY')
            self.assertFalse(row['analysis_complete']); self.assertFalse(row['original_binary_sha_rechecked'])
            self.assertNotIn(RAW, json.dumps(report)); self.assertNotIn(n['document_evidence'][0]['sha256'],json.dumps(report))
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_partial_truncated_warning_and_corrected_notice(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); n=extracted(root,truncated=True,warning=True); n['notice_kind']='정정공고'
            n['attachments'].append({'name':'second.pdf','url':'https://www.g2b.go.kr/second'})
            board(root,[n]); row=queue.read_queue(root,at=AT)['results'][0]
            self.assertTrue({'PARTIAL_EXTRACTION','TEXT_OR_TABLE_TRUNCATED','EXTRACTION_WARNING','CORRECTION_RECHECK'} <= set(row['reason_codes']))
            self.assertFalse(row['can_reevaluate_stored_text'])

    def test_sha_mismatch_conflict_version_mismatch_and_legacy_do_not_use_old_analysis(self):
        for condition, expected in [('sha','SOURCE_HASH_MISMATCH'),('conflict','SOURCE_HASH_CONFLICT'),
                                    ('version','SOURCE_VERSION_MISMATCH'),('legacy','SOURCE_VERSION_UNVERIFIED')]:
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as td:
                root=Path(td); n=extracted(root); proof=n['document_evidence'][0]
                if condition=='sha':proof['sha256']='0'*64
                if condition=='conflict':n['document_evidence'].append({**proof,'sha256':'0'*64})
                if condition=='version':proof['notice_bid_order']='000'
                if condition=='legacy':proof.pop('notice_bid_order')
                board(root,[n]); original=(root/'dashboard.json').read_bytes();r=queue.read_queue(root,at=AT)
                row=(r['results']+r['held_results'])[0]
                self.assertIn(expected,row['reason_codes']);self.assertFalse(row['can_reevaluate_stored_text'])
                self.assertEqual(original,(root/'dashboard.json').read_bytes())

    def test_cache_tamper_missing_scan_limit_and_reparse_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);n=extracted(root);board(root,[n]);p=root/'rfp_fulltext'/(n['document_evidence'][0]['fulltext_ref']+'.json')
            good=p.read_bytes();record=json.loads(good);record['chunks'][0]['text']='tampered';p.write_text(json.dumps(record))
            self.assertIn('CACHE_INVALID',queue.read_queue(root,at=AT)['results'][0]['reason_codes'])
            p.unlink();self.assertIn('CACHE_UNAVAILABLE',queue.read_queue(root,at=AT)['results'][0]['reason_codes']);p.write_bytes(good)
            with patch.object(queue,'MAX_CACHE_FILES',0):
                self.assertIn('CACHE_SCAN_LIMIT',queue.read_queue(root,at=AT)['results'][0]['reason_codes'])
            with patch.object(queue,'reject_reparse',side_effect=OSError('PRIVATE_PATH')):
                with self.assertRaisesRegex(AuditBlocked,'BLOCKED_INPUT'):queue.read_queue(root,at=AT)

    def test_cache_and_board_change_are_snapshot_blocked_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); n=extracted(root);board(root,[n]);original=queue._cache_capture;calls=0
            def altered(*args):
                nonlocal calls
                calls+=1;value=original(*args)
                return value if calls==1 else None
            with patch.object(queue,'_cache_capture',side_effect=altered):
                with self.assertRaisesRegex(AuditBlocked,'BLOCKED_SNAPSHOT'):queue.read_queue(root,at=AT)
            self.assertEqual(calls,2)
            captured=queue._capture(root)
            with patch.object(queue,'_capture',side_effect=[captured,{}]):
                with self.assertRaisesRegex(AuditBlocked,'BLOCKED_SNAPSHOT'):queue.read_queue(root,at=AT)

    def test_limit_and_omitted_count_and_bad_input(self):
        r=queue.build([notice('BID05A'),notice('BID05B')],at=AT,limit=1)
        self.assertEqual(r['omitted_count'],1)
        for bad in [None,{},[{}]*10001]:
            with self.assertRaises(ValueError):queue.build(bad,at=AT)

    def test_cache_read_size_limit_and_duplicate_json_are_not_trusted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); n=extracted(root);board(root,[n])
            p=root/'rfp_fulltext'/(n['document_evidence'][0]['fulltext_ref']+'.json')
            with patch.object(queue,'MAX_CACHE_BYTES',1):
                with self.assertRaisesRegex(AuditBlocked,'BLOCKED_INPUT'):queue.read_queue(root,at=AT)
            p.write_text('{"schema_version":1,"schema_version":1}',encoding='utf-8')
            self.assertIn('CACHE_INVALID',queue.read_queue(root,at=AT)['results'][0]['reason_codes'])

    def test_batch_records_download_and_extraction_failures_without_retry(self):
        for phase in ['DOWNLOAD','EXTRACTION']:
            calls=[]
            def fetch(url):
                calls.append(url)
                if phase=='DOWNLOAD':raise OSError(RAW)
                return b'synthetic'
            def parser(name,raw):raise ValueError(RAW)
            result=analyze(notice(),parser,fetcher=fetch)
            self.assertEqual(len(calls),1);self.assertEqual(result['document_evidence'][0]['failure_stage'],phase)
            self.assertNotIn(RAW,repr(result))
            row=queue.build([{**notice(),**result}],at=AT)['results'][0]
            self.assertIn('DOWNLOAD_FAILED' if phase=='DOWNLOAD' else 'EXTRACTION_FAILED',row['reason_codes'])


if __name__=='__main__':unittest.main()
