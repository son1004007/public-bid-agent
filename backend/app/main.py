"""FastAPI의 공개 데모 검색 API 경계.

목적/책임: health, 합성 공고 검색·상세 조회의 입력/응답/오류 계약을 제공한다.
입력/출력: GET /api/health, GET /api/notices, GET /api/notices/{notice_id}.
신뢰 경계/권한: 인증과 데이터 변경 기능은 제공하지 않는다. 사용자 입력을 Query/Path로 검증한다.
상태 변경/부작용: 없음. 합성 fixture만 읽는다.
실패/타임아웃/재시도: 결손/변조된 fixture는 503이며 정상 0건과 구분한다.
핵심 불변조건: 외부 공고/API 연결 또는 실제 접수 가능 판정은 구현하지 않았다.
관련 요구사항/테스트/설계 문서: REQ-BID-001, backend/tests/test_api.py.
"""

import logging
from typing import Annotated

from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .repository import find_notices, get_notice
from .schemas import Notice, NoticeCategory, NoticeSearchResponse

logger = logging.getLogger(__name__)
app = FastAPI(title="Public Bid Agent - Synthetic Demo", version="0.1.0")


@app.exception_handler(ValueError)
async def invalid_fixture_handler(_request, _exc: ValueError):
    logger.error("synthetic fixture invalid")
    return JSONResponse(status_code=503, content={"detail": "Demo data temporarily unavailable"})


@app.exception_handler(ValidationError)
async def invalid_schema_handler(_request, _exc: ValidationError):
    logger.error("synthetic fixture schema invalid")
    return JSONResponse(status_code=503, content={"detail": "Demo data temporarily unavailable"})


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_source": "SYNTHETIC_FIXTURE"}


@app.get("/api/notices", response_model=NoticeSearchResponse)
def search_notices(
    q: Annotated[str, Query(max_length=120, description="제목, 기관, 기술 키워드")] = "",
    category: NoticeCategory | None = None,
) -> NoticeSearchResponse:
    items = find_notices(query=q, category=category)
    return NoticeSearchResponse(items=items, total=len(items))


@app.get("/api/notices/{notice_id}", response_model=Notice)
def read_notice(
    notice_id: Annotated[str, Path(min_length=1, max_length=64, pattern=r"^demo-[a-z0-9-]+$")],
) -> Notice:
    notice = get_notice(notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    return notice
