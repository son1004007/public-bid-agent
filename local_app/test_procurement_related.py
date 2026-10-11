"""공식 면허, 참가 지역, e발주 첨부 API에 대한 가상 응답 검증."""
import unittest
from unittest.mock import patch
import procurement_related as related
import dashboard_backend as backend


def packet(rows):
    return {"response":{"header":{"resultCode":"00"},
            "body":{"items":rows,"totalCount":len(rows)}}}


class RelatedTests(unittest.TestCase):
    def test_whitelisted_operations(self):
        payloads=[
            packet([{"lcnsLmtNm":"소프트웨어사업자","permsnIndstrytyList":"SW업종"}]),
            packet([{"prtcptPsblRgnNm":"전국"}]),
            packet([{"eorderAtchFileNm":"제안요청서.hwpx",
                "eorderAtchFileUrl":"https://www.g2b.go.kr/docs/a.hwpx",
                "eorderDocDivNm":"제안요청서"}])]
        with patch.object(related,"_fetch_json",side_effect=payloads) as call:
            data=related.fetch("TEST-VALID-STRING-1234567890","R26BK01700000","000")
        self.assertEqual(call.call_count,3)
        self.assertEqual(data["licenses"][0]["name"],"소프트웨어사업자")
        self.assertEqual(data["regions"][0]["name"],"전국")
        self.assertEqual(data["attachments"][0]["name"],"제안요청서.hwpx")
        endpoints=[v.kwargs["endpoint"] for v in call.call_args_list]
        self.assertEqual(len(set(endpoints)),3)
        self.assertTrue(all(e.startswith(related.BASE) for e in endpoints))

    def test_incomplete_official_reply_fails_closed(self):
        with patch.object(related,"_fetch_json",side_effect=[
            packet([]),packet([]),{"response":{"header":{"resultCode":"20"},"body":{}}}]):
            with self.assertRaises(backend.ProviderError):
                related.fetch("TEST-VALID-STRING-1234567890","R26BK01700000","000")

    def test_external_attachment_host_dropped(self):
        with patch.object(related,"_fetch_json",side_effect=[
            packet([]),packet([]),packet([{"eorderAtchFileNm":"제안요청서.pdf",
                "eorderAtchFileUrl":"https://unrelated.example/file.pdf"}])]):
            value=related.fetch("TEST-VALID-STRING-1234567890","R26BK01700000","000")
        self.assertEqual(value["attachments"],[])


if __name__=="__main__":
    unittest.main()
