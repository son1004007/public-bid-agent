"""공식 RFP 원본 로컬 업로드 검증 흐름.
입력: dashboard 공고, 사용자가 선택한 비공개 원본 바이트 및 저장된 evidence identity.
출력: 원본·증거·캐시와 현재 파서 재실행 상태(고정 enum/정수만).
신뢰 경계: 공식 attachment/proof로 명칭·출처를 결속; 취소/구차수/STALE은 차단.
부작용: 파일 저장·외부 네트워크/모델 전송·사람 결정 변경 없음; 캐시 읽기만.
실패: 애매한 버전/원본 파일 변경/불완전 파서는 판정 보류; 데이터 노출 금지.
불변: 재현 상태는 원본 전체 의미·표·각주/OCR 커버리지나 적격성을 확정하지 않음.
관련: rfp_original_compare.py, test_rfp_original_workflow.py, D-06/07/17.
"""
import re

from notice_lifecycle import is_cancel_kind
from rfp_fulltext import load
from rfp_original_compare import compare


def verify(notice, root, identity, raw, parser):
    """서버에서 읽은 특정 공고의 공식 첨부와 증거만 사용하고 고정 진단값 반환."""
    if not isinstance(notice, dict) or not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{64}", identity):
        return {"status": "INVALID_EVIDENCE"}
    if (notice.get("notice_lifecycle") in ("CANCELLED", "SUPERSEDED", "REVIEW")
            or is_cancel_kind(notice.get("notice_kind"))
            or notice.get("rfp_review_status") == "STALE"):
        return {"status": "NOTICE_REVIEW_BLOCKED"}
    if notice.get("document_status") != "EXTRACTED":
        return {"status": "ORIGINAL_NOT_EXTRACTED"}
    attachments = notice.get("attachments")
    evidence = notice.get("document_evidence")
    if not isinstance(attachments, list) or not isinstance(evidence, list):
        return {"status": "INVALID_EVIDENCE"}
    # 저장된 첨부의 identity 자체를 믿지 않고 compare()에서 공식 URL/파일명 재계산.
    from hashlib import sha256
    official = [a for a in attachments[:120] if isinstance(a,dict)
                and isinstance(a.get("name"),str) and isinstance(a.get("url"),str)
                and sha256((a["url"]+"\n"+a["name"]).encode()).hexdigest()==identity]
    proofs = [p for p in evidence[:120] if isinstance(p,dict)
              and p.get("identity")==identity and p.get("status")=="EXTRACTED"]
    if len(official)!=1 or len(proofs)!=1:
        return {"status": "EVIDENCE_AMBIGUOUS_OR_MISSING"}
    proof = proofs[0]
    # 과거 증거는 공고 버전 메타데이터가 없다. 동일 URL/파일명이
    # 다른 공고나 차수에서 재사용될 수 있으므로 추정하지 않고 보류한다.
    if not all(isinstance(notice.get(k),str) and notice[k] for k in ("id","bid_no","bid_order")):
        return {"status":"PROVENANCE_VERSION_UNVERIFIED"}
    if (proof.get("notice_id") != notice["id"]
            or proof.get("notice_bid_no") != notice["bid_no"]
            or proof.get("notice_bid_order") != notice["bid_order"]):
        return {"status":"PROVENANCE_VERSION_UNVERIFIED"}
    reference = proof.get("fulltext_ref")
    if not isinstance(reference,str) or not re.fullmatch(r"[a-f0-9]{64}",reference):
        return {"status": "CACHE_MISMATCH"}
    try:
        cache = load(root,reference)
    except (ValueError, OSError, UnicodeError, TypeError, KeyError):
        return {"status": "CACHE_MISMATCH"}
    return compare(official[0],proof,cache,raw,parser)
