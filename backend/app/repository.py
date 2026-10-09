"""읽기 전용 합성 공고 데이터 저장소.

목적/책임: 버전 관리된 fixture를 로딩하고, 단순 검색을 수행한다.
입력/출력: UTF-8 JSON -> 검증된 Notice 목록.
신뢰 경계/권한: 외부 API 또는 임의 URL은 호출하지 않으며 fixture 전체를 Pydantic으로 검증한다.
상태 변경/부작용: 최초 읽기 이후 변경 없음. 공용 lru_cache 사용.
실패/타임아웃/재시도: 파일/스키마 오류를 빈 목록으로 바꾸지 않는다.
핵심 불변조건: 각 ID 유일, 외부 실공고로 오인 가능한 링크와 접수 확정 상태가 없다.
관련 요구사항/테스트/설계 문서: REQ-BID-001, backend/tests/test_repository.py.
"""

import json
from functools import lru_cache
from pathlib import Path

from .schemas import Notice, NoticeCategory

_FIXTURE_FILE = Path(__file__).parent / "data" / "sample_notices.json"


@lru_cache(maxsize=1)
def load_notices() -> tuple[Notice, ...]:
    contents = json.loads(_FIXTURE_FILE.read_text(encoding="utf-8"))
    if not isinstance(contents, list):
        raise ValueError("fixture root must be a list")
    items = tuple(Notice.model_validate(item) for item in contents)
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate fixture notice IDs")
    return items


def find_notices(query: str = "", category: NoticeCategory | None = None) -> list[Notice]:
    term = query.strip().casefold()
    found = []
    for item in load_notices():
        searchable = " ".join((item.title, item.organization, item.summary, *item.technologies)).casefold()
        if category is not None and item.category != category:
            continue
        if term and term not in searchable:
            continue
        found.append(item)
    return found


def get_notice(notice_id: str) -> Notice | None:
    return next((item for item in load_notices() if item.id == notice_id), None)
