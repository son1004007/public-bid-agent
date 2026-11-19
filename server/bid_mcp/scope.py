"""MCP 읽기 도구 공통 검증 계약.

목적/책임: 공개 공고 전용 호출의 입력 크기·상태 플래그·출력 필드를 제한한다.
입력/출력: 문자열/제한 숫자 -> 검증된 값 또는 ValueError.
신뢰 경계: MCP 도구 인수는 LLM이 제공한 불신 입력, 실제 DB 접근 전에 확인한다.
상태 변경/부작용: 없음.
실패/타임아웃/재시도: 잘못된 인수는 즉시 거절, 임의 재시도 없음.
핵심 불변조건: 비공개 증빙, 원가, 직원, 인증정보 및 URL 직접 사용 없음.
관련: docs/server-migration/14-bid-mcp-interface.md.
"""
import os
import re

PUBLIC_SOURCE = "G2B_OFFICIAL_API"
_MAX_LIMIT = 10
_MAX_QUERY = 80
_NOTICE_NUMBER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{2,99}$")


def require_enabled() -> None:
    if os.environ.get("BID_MCP_ENABLED") != "1" or os.environ.get("BID_MCP_PUBLIC_ONLY") != "1":
        raise PermissionError("MCP_DISABLED")


def validate_query(query: str) -> str:
    if not isinstance(query, str) or any(ord(ch) < 32 or ord(ch) == 127 for ch in query):
        raise ValueError("INVALID_QUERY")
    query = query.strip()
    if not 2 <= len(query) <= _MAX_QUERY:
        raise ValueError("INVALID_QUERY")
    return query


def validate_notice_number(notice_number: str) -> str:
    if not isinstance(notice_number, str) or not _NOTICE_NUMBER.fullmatch(notice_number):
        raise ValueError("INVALID_NOTICE_NUMBER")
    return notice_number


def validate_limit(limit: int) -> int:
    if type(limit) is not int or not 1 <= limit <= _MAX_LIMIT:
        raise ValueError("INVALID_LIMIT")
    return limit


def approved_public_rfp_enabled() -> bool:
    return os.environ.get("BID_MCP_PUBLIC_RFP_ENABLED") == "1"
