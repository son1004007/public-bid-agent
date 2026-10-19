"""BID-04 HTTP 경계: 합성 임시 자료만 사용해 집계·오류·Host·원본 불변을 검증한다."""
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import server
from bid_now_audit_cli import AuditBlocked
from test_local_acceptance import synthetic_server, RAW, TITLE


class AuditHTTPTests(unittest.TestCase):
    def test_real_get_aggregate_and_source_bytes_unchanged(self):
        with synthetic_server(bid_now=True) as fixture:
            root=fixture['root']
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with urlopen(fixture['base']+'/api/dashboard/bid-now-audit',timeout=10) as response:
                self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
                body=response.read().decode('utf-8')
            report=json.loads(body)['audit']
            self.assertEqual(report['total_notices'],6)
            self.assertEqual(report['active_notice_count'],3)
            self.assertEqual(report['snapshot_check'],'STABLE_OBSERVED_READS')
            self.assertEqual(report['status'],'BLOCKED_EVIDENCE')
            for private in (RAW,TITLE,str(root),fixture['notice']['id']):
                self.assertNotIn(private,body)
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_blocked_snapshot_and_untrusted_errors_are_fixed_503(self):
        with synthetic_server(bid_now=True) as fixture:
            for code in ('BLOCKED_INPUT','BLOCKED_SNAPSHOT','PRIVATE_ERROR_CANARY'):
                with patch.object(server,'audit_bid_now_local',side_effect=AuditBlocked(code)):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(fixture['base']+'/api/dashboard/bid-now-audit',timeout=5)
                    self.assertEqual(caught.exception.code,503)
                    body=json.load(caught.exception)
                    caught.exception.close()
                    self.assertEqual(body['status'],code if code!='PRIVATE_ERROR_CANARY' else 'BLOCKED_INPUT')
                    self.assertFalse(body['aggregate_available'])

    def test_host_rejected_and_missing_evidence_is_not_zero_notices(self):
        with synthetic_server(bid_now=True) as fixture:
            req=Request(fixture['base']+'/api/dashboard/bid-now-audit',headers={'Host':'attacker.invalid'})
            with self.assertRaises(HTTPError) as caught:
                urlopen(req,timeout=5)
            self.assertEqual(caught.exception.code,403)
            caught.exception.close()
            profile=fixture['root']/'department_profile.json'
            original=profile.read_bytes()
            profile.unlink()
            try:
                with urlopen(fixture['base']+'/api/dashboard/bid-now-audit',timeout=10) as response:
                    report=json.load(response)['audit']
            finally:
                profile.write_bytes(original)
            self.assertEqual(report['total_notices'],6)
            self.assertEqual(report['active_department_match_unknown_count'],3)
            self.assertEqual(report['active_augmentation_review_count'],0)


if __name__=='__main__':
    unittest.main()
