"""검색 저장소와 fixture 불변조건 테스트."""

import pytest

from app.repository import find_notices, load_notices
from app.schemas import Notice, NoticeCategory


def test_all_fixture_ids_are_unique_and_not_official():
    items = load_notices()
    assert len({notice.id for notice in items}) == len(items)
    assert all(notice.id.startswith("demo-") and notice.source_url is None for notice in items)


def test_search_casefolds_and_filters_category():
    assert len(find_notices("python")) == 2
    assert [x.category for x in find_notices("spring")] == [NoticeCategory.SW]
    assert find_notices("python", NoticeCategory.SW) == []


def test_source_cannot_be_falsified():
    data = load_notices()[0].model_dump()
    data["source_type"] = "OFFICIAL_API"
    with pytest.raises(ValueError):
        Notice.model_validate(data)


def test_status_cannot_be_falsified():
    data = load_notices()[0].model_dump()
    data["submission_status"] = "OPEN"
    with pytest.raises(ValueError):
        Notice.model_validate(data)
