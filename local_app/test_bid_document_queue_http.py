"""BID-05 HTTP: 합성 자료만 읽고 보안·비반사·상세용 ID 외 개인정보/변경 없음을 확인."""
import json
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
import server
from bid_now_audit_cli import AuditBlocked
from test_local_acceptance import synthetic_server, RAW, TITLE


class DocumentQueueHTTPTests(unittest.TestCase):
    def test_real_get_and_all_file_bytes_unchanged_no_raw_or_sha(self):
        with synthetic_server(bid_now=True) as f:
            before={p:p.read_bytes() for p in f['root'].rglob('*') if p.is_file()}
            with urlopen(f['base']+'/api/dashboard/bid-document-queue',timeout=10) as response:
                self.assertEqual(response.headers['Cache-Control'],'no-store')
                self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
                body=response.read().decode()
            q=json.loads(body)['queue'];self.assertEqual(q['total_notices'],6)
            self.assertEqual(q['dashboard_revision'],f['board']['revision'])
            # 사전등록 기한 경과도 자동 작업에서 분리하여 증빙 확인 전 보류한다.
            self.assertEqual(q['action_required_count'],2);self.assertEqual(q['held_count'],4)
            self.assertEqual(q['results'][0]['legal_eligibility'],'UNVERIFIED')
            for private in [RAW,TITLE,str(f['root']),f['notice']['document_evidence'][0]['sha256']]:self.assertNotIn(private,body)
            self.assertEqual(before,{p:p.read_bytes() for p in f['root'].rglob('*') if p.is_file()})

    def test_fixed_503_and_host_rejection_no_private_error_echo(self):
        with synthetic_server(bid_now=True) as f:
            for value in ['BLOCKED_INPUT','BLOCKED_SNAPSHOT','PRIVATE_ERROR']:
                with patch.object(server,'read_bid_document_queue',side_effect=AuditBlocked(value)):
                    with self.assertRaises(HTTPError) as e:urlopen(f['base']+'/api/dashboard/bid-document-queue',timeout=5)
                    self.assertEqual(e.exception.code,503);body=e.exception.read().decode();e.exception.close()
                    self.assertNotIn('PRIVATE_ERROR',body);self.assertFalse(json.loads(body)['queue_available'])
            request=Request(f['base']+'/api/dashboard/bid-document-queue',headers={'Host':'attacker.invalid'})
            with self.assertRaises(HTTPError) as e:urlopen(request,timeout=5)
            self.assertEqual(e.exception.code,403);e.exception.close()


if __name__=='__main__':unittest.main()
