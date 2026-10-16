"""RFP 원문 표현 후보의 사람 검토 라벨과 원본/차수 결속 여부를 로컬 분리 보존.

목적: 이미 SHA 검증한 현재 요구사항 구조화 근거만 수동 분류하고 변경 이력을 남김.
입력: 로컬 JSON 라벨 상태, 현재 공식 공고, 구조화 보고서, 제한된 요청 메타데이터.
출력: 코멘트/비공개 원문 없는 정형 라벨, 표시된 추출 후보의 검토 현황.
신뢰 경계: 사용자의 판단은 독립 원본 정답이 아니며 실제 전체 Recall/FN 산출 불가.
부작용: 순수 함수; 외부 API·AI·파일 I/O 없음. 서버만 별도 로컬 JSON 원자 저장.
실패: schema/revision/공고차수/증거 SHA/offset/텍스트 fingerprint 불일치 시 안전 거부.
불변: 사용자 입찰 결정·기존 dashboard, RFP cache, 첨부 바이너리 보존.
"""
import copy
import hashlib
import re
from datetime import datetime

from rfp_requirements import SCHEMA_VERSION

LABELS=frozenset(("SUPPORTED_SIGNAL","FALSE_POSITIVE","UNCERTAIN"))
MAX_EVENTS=2000
_HEX=re.compile(r"[a-f0-9]{64}\Z")
_ID=re.compile(r"G2B-[A-Za-z0-9-]{4,100}\Z")

class AuditConflict(ValueError):
    pass

def initial():
    return {"schema_version":1,"revision":0,"events":[]}

def validate(data):
    if not isinstance(data,dict) or type(data.get("schema_version")) is not int or data["schema_version"]!=1:
        raise ValueError("라벨 파일 버전 오류")
    if type(data.get("revision")) is not int or data["revision"]<0:
        raise ValueError("라벨 revision 오류")
    if not isinstance(data.get("events"),list) or len(data["events"])>MAX_EVENTS:
        raise ValueError("라벨 이력 상한/구조 오류")
    fields={"id","bid_no","bid_order","rfp_schema_version","category",
            "evidence","label","provenance","recorded_at","source"}
    for event in data["events"]:
        if not isinstance(event,dict) or set(event)!=fields:
            raise ValueError("라벨 이력 필드 불일치")
        if (type(event["rfp_schema_version"]) is not int or
            event["rfp_schema_version"]!=SCHEMA_VERSION or
            not isinstance(event["id"],str) or not _ID.fullmatch(event["id"]) or
            not isinstance(event["bid_no"],str) or not re.fullmatch(r"[A-Za-z0-9-]{4,32}",event["bid_no"]) or
            not isinstance(event["bid_order"],str) or not re.fullmatch(r"[0-9]{1,5}",event["bid_order"]) or
            event["category"] not in ("participation","evaluation","scope") or
            event["label"] not in LABELS or
            event["provenance"] not in ("VERSION_MATCHED","VERSION_UNVERIFIED") or
            event["source"]!="HUMAN_REVIEWED_EXTRACTED_TEXT_ONLY"):
            raise ValueError("라벨 이력 출처·분류 손상")
        _check_evidence(event["evidence"])
        _check_stamp(event["recorded_at"])
    return data

def _check_stamp(value):
    if not isinstance(value,str) or not 20<=len(value)<=48 or any(ord(c)<32 for c in value):
        raise ValueError("라벨 기록 시각 형식 오류")
    try:
        parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("라벨 기록 시각 오류") from exc
    if parsed.tzinfo is None:
        raise ValueError("라벨 시각의 시간대 필요")

def _check_evidence(evidence):
    if not isinstance(evidence,dict) or set(evidence)!={"source_sha256","fulltext_ref","offset_start","offset_end","excerpt_sha256"}:
        raise ValueError("라벨 증거 필드 오류")
    if (not isinstance(evidence["source_sha256"],str) or not _HEX.fullmatch(evidence["source_sha256"])
            or not isinstance(evidence["fulltext_ref"],str) or not _HEX.fullmatch(evidence["fulltext_ref"])
            or type(evidence["offset_start"]) is not int or type(evidence["offset_end"]) is not int
            or not 0<=evidence["offset_start"]<evidence["offset_end"]<=44000
            or not isinstance(evidence["excerpt_sha256"],str) or not _HEX.fullmatch(evidence["excerpt_sha256"])):
        raise ValueError("라벨 증거 SHA·offset 오류")

def _matching(report,request):
    category=request.get("category")
    if not isinstance(category,str) or category not in ("participation","evaluation","scope"):
        raise ValueError("현재는 3개 주요 유형의 원문 표현 라벨만 지원")
    evidence=request.get("evidence")
    if not isinstance(evidence,dict) or set(evidence)!={"source_sha256","fulltext_ref","offset_start","offset_end","excerpt_sha256"}:
        raise ValueError("근거 입력 형식 오류")
    if (not isinstance(evidence["source_sha256"],str) or not _HEX.fullmatch(evidence["source_sha256"])
            or not isinstance(evidence["fulltext_ref"],str) or not _HEX.fullmatch(evidence["fulltext_ref"])
            or type(evidence["offset_start"]) is not int or type(evidence["offset_end"]) is not int
            or not 0<=evidence["offset_start"]<evidence["offset_end"]<=44000
            or not isinstance(evidence["excerpt_sha256"],str) or not _HEX.fullmatch(evidence["excerpt_sha256"])):
        raise ValueError("근거 범위/해시 형식 오류")
    matched=[]
    for group in report["requirements"]:
        if group["category"]!=category:continue
        for item in group["items"]:
            e=item["evidence"]
            fingerprint=hashlib.sha256(e["excerpt"].encode("utf-8")).hexdigest()
            if (e["source_sha256"]==evidence["source_sha256"] and
                e["fulltext_ref"]==evidence["fulltext_ref"] and
                e["offset_start"]==evidence["offset_start"] and e["offset_end"]==evidence["offset_end"] and
                fingerprint==evidence["excerpt_sha256"]):
                matched.append(e)
    if len(matched)!=1:
        raise AuditConflict("현재 추출 증거가 바뀌었거나 동일 근거가 모호합니다. 재조회 후 확인")
    return category,evidence

def append(state,notice,report,request,stamp):
    validate(state)
    if type(request.get("expected_revision")) is not int or request["expected_revision"]!=state["revision"]:
        raise AuditConflict("RFP 검토 이력이 다른 창에서 변경되었습니다")
    if (not isinstance(notice,dict) or not isinstance(report,dict)
            or not isinstance(request.get("id"),str) or not _ID.fullmatch(request["id"])
            or request["id"]!=notice.get("id") or report.get("id")!=notice.get("id")
            or type(report.get("schema_version")) is not int or report["schema_version"]!=SCHEMA_VERSION
            or report.get("state")!="EVIDENCE_CANDIDATES"):
        raise AuditConflict("현재 공식 공고/RFP 분류 근거가 확인되지 않습니다")
    _check_stamp(stamp)
    if len(state["events"])>=MAX_EVENTS:
        raise AuditConflict("검토 이력 상한: 이전 파일 보존")
    if not isinstance(request.get("label"),str) or request["label"] not in LABELS:
        raise ValueError("검토 선택 오류")
    category,evidence=_matching(report,request)
    bid_no,bid_order=notice.get("bid_no"),notice.get("bid_order")
    if (not isinstance(bid_no,str) or not isinstance(bid_order,str)
            or not re.fullmatch(r"[A-Za-z0-9-]{4,32}",bid_no)
            or not re.fullmatch(r"[0-9]{1,5}",bid_order)):
        raise AuditConflict("공고번호·차수 미확인")
    # 근거의 현재 공고 차수 귀속은 신규 수집분만 완전 결속.
    matching_proofs=[p for p in (notice.get("document_evidence") or [])[:120]
        if isinstance(p,dict) and p.get("sha256")==evidence["source_sha256"]
        and p.get("fulltext_ref")==evidence["fulltext_ref"] and p.get("status")=="EXTRACTED"]
    provenance=("VERSION_MATCHED" if len(matching_proofs)==1 and
        matching_proofs[0].get("notice_id")==notice["id"] and
        matching_proofs[0].get("notice_bid_no")==bid_no and
        matching_proofs[0].get("notice_bid_order")==bid_order
        else "VERSION_UNVERIFIED")
    event={"id":notice["id"],"bid_no":bid_no,"bid_order":bid_order,
           "rfp_schema_version":SCHEMA_VERSION,"category":category,
           "evidence":copy.deepcopy(evidence),"label":request["label"],
           "provenance":provenance,"recorded_at":stamp,
           "source":"HUMAN_REVIEWED_EXTRACTED_TEXT_ONLY"}
    out=copy.deepcopy(state)
    out["revision"]+=1
    out["events"].append(event)
    return out

def summarize(state,notice,report):
    validate(state)
    if report.get("id")!=notice.get("id"):
        raise ValueError("현재 공고와 검토 화면이 다릅니다")
    current=set()
    for group in report.get("requirements",[]):
        if group.get("category") not in ("participation","evaluation","scope"):continue
        for item in group.get("items",[]):
            e=item["evidence"]
            if not isinstance(e.get("fulltext_ref"),str):continue
            current.add((group["category"],e["source_sha256"],e["fulltext_ref"],
                         e["offset_start"],e["offset_end"],
                         hashlib.sha256(e["excerpt"].encode("utf-8")).hexdigest()))
    records=[]
    for item in state["events"]:
        if item["id"]!=notice["id"]:continue
        proof=item.get("evidence",{})
        key=(item["category"],proof.get("source_sha256"),proof.get("fulltext_ref"),
             proof.get("offset_start"),proof.get("offset_end"),proof.get("excerpt_sha256"))
        version_matched=(item.get("bid_no")==notice.get("bid_no") and item.get("bid_order")==notice.get("bid_order"))
        records.append({"category":item["category"],"label":item["label"],
                        "status":"CURRENT_EXTRACTED_SIGNAL_ONLY" if version_matched and key in current else "STALE_REVIEW",
                        "provenance":item.get("provenance","VERSION_UNVERIFIED"),
                        "offset_start":proof.get("offset_start"),"recorded_at":item.get("recorded_at")})
    # 검토 정정의 전체 이력은 유지하되 유효 라벨 집계는 동일 근거의 마지막 선택만.
    latest={}
    for item in state["events"]:
        if item["id"]!=notice["id"]:continue
        e=item["evidence"]
        key=(item["category"],e.get("source_sha256"),e.get("fulltext_ref"),
             e.get("offset_start"),e.get("offset_end"),e.get("excerpt_sha256"))
        if (key in current and item.get("bid_no")==notice.get("bid_no")
                and item.get("bid_order")==notice.get("bid_order")):
            latest[key]=item["label"]
    counts={label:sum(1 for v in latest.values() if v==label) for label in sorted(LABELS)}
    return {"revision":state["revision"],"records":records[-60:],"current_label_counts":counts,
            "current_reviewed_unique":len(latest),"current_displayed_candidates":len(current),
            "current_unreviewed_displayed":max(0,len(current)-len(latest)),
            "metrics_state":"NOT_MEASURABLE_WITHOUT_INDEPENDENT_ORIGINAL_GROUND_TRUTH",
            "false_negatives":"NOT_ASSESSED","recall":"NOT_MEASURABLE",
            "original_pages_tables_ocr":"NOT_VERIFIED"}
