"""Narrow G2B public notice URL projection; never broaden attachment URLs."""
from django.test import SimpleTestCase
from bid_server.procurement.serializers import public_notice_url, public_source_url

class PublicNoticeLinkTests(SimpleTestCase):
    valid = "https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=R26BK00000001&bidPbancOrd=001"
    def test_exact_route_and_identity(self):
        self.assertEqual(public_notice_url(self.valid,"R26BK00000001","1"),self.valid)
        self.assertEqual(public_notice_url(self.valid,"R26BK00000001","001"),self.valid)
        self.assertEqual(public_source_url(self.valid),"")
        self.assertEqual(public_notice_url(self.valid,"R26BK00000002","1"),"")
        self.assertEqual(public_notice_url(self.valid,"R26BK00000001","2"),"")
        self.assertEqual(public_notice_url(self.valid,"R26BK00000001",None),"")
    def test_reject_untrusted_parameters_and_route(self):
        for value in (self.valid+"&ServiceKey=fixture",self.valid+"&bidPbancOrd=002",
                      self.valid.replace("001","%30%30%31"), self.valid.replace("www.g2b.go.kr","foo.g2b.go.kr"),
                      self.valid.replace("/single/","/redirect/"),self.valid.replace("https:","http:"),
                      self.valid.replace("www.g2b.go.kr","user@www.g2b.go.kr"),self.valid+"#fragment"):
            with self.subTest(value=value):
                self.assertEqual(public_notice_url(value,"R26BK00000001","1"),"")
    def test_existing_plain_link_contract_unchanged(self):
        self.assertEqual(public_notice_url("https://g2b.go.kr/synthetic","SYNTHETIC",None),"https://g2b.go.kr/synthetic")
