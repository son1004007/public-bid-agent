"""공식 RFP 첨부 보존 한계(40개·동일 URL)를 검증하는 합성 회귀.

입력/출력: 합성 공고 dict만 사용하며 로컬 사용자 JSON을 읽거나 저장하지 않는다.
불변조건: 기존 상세 첨부, 출처, 메타데이터, 사람 결정/이력, 원본 입력을 보존한다.
"""
import copy
import unittest

from dashboard_backend import blank, normalize, update_collection, merge_attachments, MAX_STORED_ATTACHMENTS

URL="https://www.g2b.go.kr/pn/files/"
BASE={"bidNtceNo":"R26BK01234567","bidNtceOrd":"001","bidNtceNm":"AI SW 구축"}


class AttachmentPreservationTests(unittest.TestCase):
    def _state(self):
        state=blank()
        notice=normalize(BASE)
        notice["final"]="no_bid"
        state["notices"]=[notice]
        state["history"]=[{"note":"human-decision"}]
        return state

    def test_incoming_forty_cannot_evict_saved_rfp_attachment(self):
        old=self._state()
        preserved={"url":URL+"rfp.pdf","name":"기존 상세 RFP.pdf",
                   "source":"공식 상세","identity":"verified-rfp-identity"}
        old["notices"][0]["attachments"]=[preserved]
        incoming=normalize(BASE)
        incoming["attachments"]=[
            {"url":URL+str(i)+".pdf","name":str(i)+".pdf","source":"목록"}
            for i in range(40)]
        snapshot=copy.deepcopy(old)
        merged=update_collection(old,[incoming],1,"SYNTHETIC")
        result=merged["notices"][0]
        self.assertEqual(len(result["attachments"]),41)
        self.assertEqual(result["attachments"][0],preserved)
        self.assertEqual(result["final"],"no_bid")
        self.assertEqual(merged["history"],snapshot["history"])
        self.assertEqual(old,snapshot)

    def test_existing_forty_plus_new_rfp_remain_after_later_recrawl(self):
        old=self._state()
        old["notices"][0]["attachments"]=[
            {"url":URL+str(i)+".pdf","name":"공고 첨부 "+str(i)+".pdf"}
            for i in range(40)]
        extra={"url":URL+"new-rfp.pdf","name":"제안요청서.pdf",
               "source":"공식 상세","identity":"synthetic-rfp"}
        old["notices"][0]["attachments"]=merge_attachments(
            old["notices"][0]["attachments"],[extra])
        self.assertEqual(len(old["notices"][0]["attachments"]),41)
        refreshed=normalize(BASE)
        refreshed["attachments"]=[
            {"url":URL+str(i)+".pdf","name":"공고 첨부 "+str(i)+".pdf"}
            for i in range(40)]
        result=update_collection(old,[refreshed],40,"SYNTHETIC")
        self.assertEqual(len(result["notices"][0]["attachments"]),41)
        self.assertIn(extra,result["notices"][0]["attachments"])
        self.assertEqual(result["history"],old["history"])

    def test_attachment_capacity_refuses_to_silently_erase_evidence(self):
        full=[{"url":URL+str(i),"name":"공식 근거"} for i in range(MAX_STORED_ATTACHMENTS)]
        snapshot=copy.deepcopy(full)
        with self.assertRaises(ValueError):
            merge_attachments(full,[{"url":URL+"overflow","name":"신규 RFP"}])
        self.assertEqual(full,snapshot)

    def test_same_url_matching_second_identity_updates_second_only(self):
        from dashboard_backend import merge_attachments
        a={"url":URL+"same.pdf","identity":"A","name":"RFP A"}
        b={"url":URL+"same.pdf","identity":"B","name":"RFP B"}
        saved=merge_attachments([a,b],[
            {"url":URL+"same.pdf","identity":"B","classification":"SW"}])
        self.assertEqual(len(saved),2)
        self.assertNotIn("classification",saved[0])
        self.assertEqual(saved[1]["classification"],"SW")
        self.assertEqual((saved[0]["identity"],saved[1]["identity"]),("A","B"))

    def test_two_existing_evidence_records_sharing_url_remain_distinct(self):
        old=self._state()
        first={"url":URL+"same.pdf","name":"제안요청서","source":"공식 상세",
               "identity":"sha-rfp"}
        second={"url":URL+"same.pdf","name":"별첨 요구사항","source":"공식 상세",
                "identity":"sha-annex"}
        old["notices"][0]["attachments"]=[first,second]
        fresh=normalize(BASE)
        fresh["attachments"]=[]
        snapshot=copy.deepcopy(old)
        result=update_collection(old,[fresh],1,"SYNTHETIC")
        saved=result["notices"][0]["attachments"]
        self.assertEqual(saved,[first,second])
        self.assertEqual(result["history"],snapshot["history"])
        self.assertEqual(old,snapshot)

    def test_new_notice_applies_lossless_bounded_attachment_policy(self):
        fresh=normalize(BASE)
        fresh["attachments"]=[{"url":URL+str(i)+".pdf","name":str(i)}
                              for i in range(41)]
        saved=update_collection(blank(),[fresh],41,"SYNTHETIC")["notices"][0]
        self.assertEqual(len(saved["attachments"]),41)
        self.assertEqual(saved["attachments"][0]["name"],"0")
        self.assertEqual(saved["attachments"][-1]["name"],"40")
        original=copy.deepcopy(fresh)
        overflow=normalize(BASE)
        overflow["attachments"]=[
            {"url":URL+str(i)+".pdf","name":str(i)}
            for i in range(MAX_STORED_ATTACHMENTS+1)]
        with self.assertRaises(ValueError):
            update_collection(blank(),[overflow],121,"SYNTHETIC")
        self.assertEqual(fresh,original)

    def test_url_less_named_attachment_survives_recrawl(self):
        old=self._state()
        saved_name={"url":None,"name":"공식 첨부명만 제공","source":"공고규격서"}
        old["notices"][0]["attachments"]=[saved_name]
        fresh=normalize(BASE)
        fresh["attachments"]=[{"url":None,"name":"신규 명칭만 존재","source":"공고규격서"}]
        result=update_collection(old,[fresh],1,"SYNTHETIC")["notices"][0]
        self.assertEqual(len(result["attachments"]),2)
        self.assertEqual(result["attachments"][0],saved_name)

    def test_incoming_duplicate_url_preserves_distinct_new_evidence(self):
        old=self._state()
        old["notices"][0]["attachments"]=[]
        incoming=normalize(BASE)
        incoming["attachments"]=[
            {"url":URL+"same.pdf","name":"제안요청서",
             "source":"공식 상세","identity":"rfp-sha"},
            {"url":URL+"same.pdf","name":"별첨 요구사항",
             "source":"공식 상세","identity":"annex-sha"}]
        saved=update_collection(old,[incoming],2,"SYNTHETIC")["notices"][0]["attachments"]
        self.assertEqual(len(saved),2)
        self.assertEqual({x["identity"] for x in saved},{"rfp-sha","annex-sha"})

    def test_partial_recrawl_does_not_delete_official_metadata(self):
        old=self._state()
        old["notices"][0]["org"]="기존 조달기관"
        old["notices"][0]["end"]="2026-12-01 18:00"
        old["notices"][0]["title"]="원본 보존 제목"
        fresh=normalize(BASE)
        fresh["org"]=None
        fresh["end"]=""
        fresh["title"]=None
        result=update_collection(old,[fresh],1,"SYNTHETIC")
        notice=result["notices"][0]
        self.assertEqual(notice["org"],"기존 조달기관")
        self.assertEqual(notice["end"],"2026-12-01 18:00")
        self.assertEqual(notice["title"],"원본 보존 제목")

    def test_same_url_different_sources_without_identity_remain_separate(self):
        old=self._state()
        old["notices"][0]["attachments"]=[
            {"url":URL+"same.pdf","name":"RFP","source":"상세"}]
        fresh=normalize(BASE)
        fresh["attachments"]=[
            {"url":URL+"same.pdf","name":"별첨","source":"목록"}]
        attachments=update_collection(old,[fresh],1,"SYNTHETIC")["notices"][0]["attachments"]
        self.assertEqual(len(attachments),2)
        self.assertEqual([x["source"] for x in attachments],["상세","목록"])

    def test_same_url_keeps_original_rfp_metadata_and_fills_missing_fields(self):
        old=self._state()
        preserved={"url":URL+"same.pdf","name":"상세 RFP.pdf",
                   "source":"공식 상세","identity":"original-sha",
                   "note":"기존 검증 근거"}
        old["notices"][0]["attachments"]=[preserved]
        incoming=normalize(BASE)
        incoming["attachments"]=[{"url":URL+"same.pdf","name":"축약 공고첨부.pdf",
                                 "source":"공고 목록","classification":"SW"}]
        saved=update_collection(old,[incoming],1,"SYNTHETIC")["notices"][0]["attachments"]
        self.assertEqual(len(saved),2)
        self.assertEqual(saved[0]["name"],"상세 RFP.pdf")
        self.assertEqual(saved[0]["source"],"공식 상세")
        self.assertEqual(saved[0]["identity"],"original-sha")
        self.assertEqual(saved[0]["note"],"기존 검증 근거")
        self.assertNotIn("classification",saved[0])
        self.assertEqual(saved[1]["classification"],"SW")
        self.assertEqual(saved[1]["name"],"축약 공고첨부.pdf")
        self.assertNotIn("classification",old["notices"][0]["attachments"][0])


if __name__=="__main__":
    unittest.main()
