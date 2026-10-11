"""조달청 공식 면허제한·참가가능지역·e발주 문서 목록 조회.

입력: 기존 공식 API에서 확인된 공고번호/차수와 로컬 DPAPI 인증키.
출력: 법적 자격을 확정하지 않은 공개 제한 목록/공식 다운로드 링크.
신뢰경계: 허용된 고정 조달청 API 3개 오퍼레이션만 요청, 사용자 임의 URL 금지.
부작용: 공개 API에 읽기 요청 3회, 인증키는 반환/저장/로그에 남기지 않음.
실패: 한 오퍼레이션이라도 오류/부분응답이면 과거 상세 결과를 덮어쓰지 않음.
"""
import re

from dashboard_backend import _fetch_json, ProviderError
from procurement_documents import official_url

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService/"
OPS = {
    "licenses": "getBidPblancListInfoLicenseLimit",
    "regions": "getBidPblancListInfoPrtcptPsblRgn",
    "attachments": "getBidPblancListInfoEorderAtchFileInfo",
}
MAX_ROWS = 100


def _field(value, length=250):
    return value.strip()[:length] if isinstance(value, str) else ""


def _items(document):
    response=document.get("response") if isinstance(document,dict) else None
    if not isinstance(response,dict) or not isinstance(response.get("header"),dict):
        raise ProviderError("공식 참가자격 상세 응답 형식 오류")
    if _field(response["header"].get("resultCode"))!="00":
        raise ProviderError("공식 참가자격 상세 조회 오류")
    body=response.get("body")
    if not isinstance(body,dict):
        raise ProviderError("참가자격 상세 body 오류")
    items=body.get("items")
    if isinstance(items,dict):items=items.get("item")
    if items is None:items=[]
    if isinstance(items,dict):items=[items]
    if not isinstance(items,list) or any(not isinstance(x,dict) for x in items):
        raise ProviderError("참가자격 목록 형식 오류")
    total=body.get("totalCount")
    try:
        count=int(total)
    except (TypeError,ValueError) as error:
        raise ProviderError("공고 상세 총건수 오류") from error
    if count>MAX_ROWS or len(items)<count:
        raise ProviderError("공고 상세 페이지에 누락 자료가 있습니다")
    return items


def fetch(key, bid_no, bid_order, transport=None):
    if not re.fullmatch(r"[0-9A-Za-z-]{4,32}",str(bid_no)):
        raise ValueError("공식 공고번호 오류")
    if not re.fullmatch(r"[0-9]{1,5}",str(bid_order)):
        raise ValueError("공고 차수 오류")
    from procurement_credentials import clean_key
    try:key=clean_key(key)
    except ValueError as error:raise ProviderError("인증키 입력 형식 오류") from error
    raw={}
    for part,operation in OPS.items():
        query={"ServiceKey":key,"type":"json","inqryDiv":"2","bidNtceNo":bid_no,
               "bidNtceOrd":bid_order,"numOfRows":str(MAX_ROWS),"pageNo":"1"}
        raw[part]=_items(_fetch_json(query,transport=transport,endpoint=BASE+operation))
    licenses=[{"name":_field(x.get("lcnsLmtNm")),"allowed":_field(x.get("permsnIndstrytyList"),1200)}
              for x in raw["licenses"]]
    regions=[{"name":_field(x.get("prtcptPsblRgnNm"))} for x in raw["regions"]]
    docs=[]
    for x in raw["attachments"]:
        name=_field(x.get("eorderAtchFileNm"),200)
        link=x.get("eorderAtchFileUrl")
        if not isinstance(link,str) or not official_url(link):
            continue
        docs.append({"name":name or "e발주 제안요청서","url":link[:1000],
                     "source":_field(x.get("eorderDocDivNm"),60) or "e발주"})
    return {"licenses":licenses,"regions":regions,"attachments":docs}
