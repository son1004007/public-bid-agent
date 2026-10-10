"""합성 공고의 정상/오류/미검증 상태 API 계약 회귀 테스트."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_synthetic_source():
    assert client.get("/api/health").json() == {"status": "ok", "data_source": "SYNTHETIC_FIXTURE"}


def test_search_returns_explicit_fixture_disclaimer():
    response = client.get("/api/notices")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["data_source"] == "SYNTHETIC_FIXTURE"
    assert "합성" in body["disclaimer"]
    for item in body["items"]:
        assert item["source_type"] == "SYNTHETIC_FIXTURE"
        assert item["source_url"] is None
        assert item["submission_status"] == "UNKNOWN"
        assert item["source_freshness"] == "UNKNOWN"


def test_keyword_and_category_filters():
    response = client.get("/api/notices", params={"q": "FastAPI", "category": "AI"})
    assert response.status_code == 200
    assert {x["id"] for x in response.json()["items"]} == {"demo-ai-001", "demo-ai-004"}


def test_no_match_is_not_upstream_failure():
    response = client.get("/api/notices", params={"q": "없는 검색어"})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_detail_lookup_and_missing_notice():
    response = client.get("/api/notices/demo-sw-002")
    assert response.status_code == 200
    assert response.json()["category"] == "SW"
    assert client.get("/api/notices/demo-sw-999").status_code == 404


def test_rejects_unbounded_or_invalid_query():
    assert client.get("/api/notices", params={"q": "a" * 121}).status_code == 422
    assert client.get("/api/notices", params={"category": "UNSAFE"}).status_code == 422
    assert client.get("/api/notices/../../etc/passwd").status_code in {404, 422}
    assert client.get("/api/notices/invalid-id").status_code == 422


def test_missing_fixture_is_503_not_empty(monkeypatch):
    import app.main as api

    def unavailable(**_kwargs):
        raise ValueError("missing fixture")

    monkeypatch.setattr(api, "find_notices", unavailable)
    response = client.get("/api/notices")
    assert response.status_code == 503
    assert response.json() == {"detail": "Demo data temporarily unavailable"}
