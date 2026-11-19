from django.test import SimpleTestCase
from bid_server.procurement.serializers import public_attachment_url,public_source_url

class AttachmentLinkTests(SimpleTestCase):
    url="https://www.g2b.go.kr/pn/pnp/pnpe/UntyAtchFile/downloadFile.do?bidPbancNo=R26BK00000001&bidPbancOrd=001&fileSeq=1&prcmBsneSeCd=03&fileType="
    def test_exact(self):
        self.assertEqual(public_attachment_url(self.url,"R26BK00000001","1"),self.url)
        self.assertEqual(public_source_url(self.url),"")
        self.assertEqual(public_attachment_url(self.url,"R26BK00000002","1"),"")
        self.assertEqual(public_attachment_url(self.url,"R26BK00000001","2"),"")
    def test_reject(self):
        for url in (self.url+"&secret=x",self.url.replace("fileType=","fileType=secret"), self.url.replace("fileSeq=1","fileSeq=0"),self.url.replace("prcmBsneSeCd=03","prcmBsneSeCd=99"),self.url.replace("www.g2b.go.kr","evil.invalid"),self.url.replace("001","%30%30%31"),self.url+"#x"):
            self.assertEqual(public_attachment_url(url,"R26BK00000001","1"),"")
