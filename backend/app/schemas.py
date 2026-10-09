"""공고 검색 응답 계약.

목적/책임: 합성 공고의 검색 및 상세 조회에서 허용하는 출력 필드만 정의한다.
입력/출력: 검증된 fixture의 필드를 안전한 Pydantic DTO로 변환한다.
신뢰 경계/권한: 실제 조달 공고와 합성 데이터를 절대 혼동하지 않도록 source_type을 고정한다.
상태 변경/부작용: 없음.
실패/타임아웃/재시도: 잘못된 fixture는 검증 오류를 발생시킨다.
핵심 불변조건: 본 스프린트에서는 모든 공고의 접수 가능성과 원천 최신성을 확인하지 않는다.
관련 요구사항/테스트/설계 문서: REQ-BID-001, backend/tests/test_api.py, docs/07-agile-development-workflow.md.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class NoticeCategory(StrEnum):
    AI = "AI"
    SW = "SW"
    DATA = "DATA"


class Notice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^demo-[a-z0-9-]+$", max_length=64)
    title: str = Field(min_length=1, max_length=180)
    organization: str = Field(min_length=1, max_length=100)
    category: NoticeCategory
    summary: str = Field(min_length=1, max_length=500)
    technologies: list[str] = Field(max_length=10)
    source_type: str = Field(pattern=r"^SYNTHETIC_FIXTURE$")
    source_url: None = None
    submission_status: str = Field(pattern=r"^UNKNOWN$")
    source_freshness: str = Field(pattern=r"^UNKNOWN$")


class NoticeSearchResponse(BaseModel):
    items: list[Notice]
    total: int = Field(ge=0)
    data_source: str = "SYNTHETIC_FIXTURE"
    disclaimer: str = "합성 데모 데이터입니다. 실제 나라장터 공고 또는 접수 가능한 입찰이 아닙니다."
