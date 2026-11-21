"""공통 응답 설계 계약.

목적: DRF의 원시 view data를 단건 또는 목록 envelope로 한 번 감싼다.
입력/출력: 서버 view data/명시 PageResponse -> data/page/request_id JSON bytes.
경계: 숫자 계산을 하지 않고 Decimal을 문자열로 전달한다. 오류는 고정 오류 builder만 사용.
부작용/실패: 저장 없음. 비직렬화 결과는 Django500 경계가 처리한다.
불변조건: total 미확인은 null, request_id는 서버값,204는 body 없음.
관련: docs/server-migration/18, server/openapi.json, tests/test_api.py.
"""
from decimal import Decimal
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder
from .errors import request_id


class ContractEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class PageResponse(Response):
    def __init__(self, data: list, *, next_cursor: str | None = None, total: int | None = None):
        if not isinstance(data, list):
            raise TypeError("PageResponse requires a list")
        if total is not None and (isinstance(total, bool) or not isinstance(total, int) or total < 0):
            raise ValueError("Invalid page total")
        if next_cursor is not None and (not isinstance(next_cursor, str) or not next_cursor):
            raise ValueError("Invalid page cursor")
        super().__init__(data)
        self.contract_page = {"next_cursor": next_cursor, "total": total}


class EnvelopeJSONRenderer(JSONRenderer):
    encoder_class = ContractEncoder

    def render(self, data, accepted_media_type=None, renderer_context=None):
        context = renderer_context or {}
        request = context["request"]
        response = context["response"]
        if response.status_code in (204, 304):
            return b""
        if getattr(response, "contract_error", False):
            envelope = {**data, "request_id": request_id(request)}
        else:
            envelope = {"data": data, "request_id": request_id(request)}
            if hasattr(response, "contract_page"):
                envelope["page"] = response.contract_page
        return super().render(envelope, accepted_media_type, context)
