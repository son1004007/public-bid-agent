"""읽기 전용 MCP stdio 서버 진입점.

목적/책임: 공고 및 승인된 공개 RFP 근거만 MCP 도구로 제공.
입력/출력: MCP stdio JSON-RPC 요청 -> 최소 필드 JSON; 표준출력은 프로토콜 전용.
신뢰 경계: 전용 프로세스/DB 읽기 계정 경계, OFF 기본값; 네트워크 포트 미개방.
상태 변경/부작용: 조회 외 없음; 외부 LLM 및 회사 자료 전송 없음.
실패/타임아웃/재시도: 민감 오류 미노출, 외부 재시도 및 자동 공급자 전환 없음.
핵심 불변조건: 툴 입력을 DB/쉘 명령으로 실행하지 않음; 원가/사내 인력/승인/투찰 도구 없음.
관련: docs/server-migration/14-bid-mcp-interface.md.
"""
import os
from mcp.server import MCPServer

from bid_mcp.scope import require_enabled
from bid_mcp import service

mcp = MCPServer("public-bid-agent-public-readonly")


def _call(func, **kwargs):
    try:
        require_enabled()
        return func(**kwargs)
    except (PermissionError, ValueError) as exc:
        return {"status": "DENIED", "reason": str(exc)}
    except Exception:
        # DB exception detail might contain internal paths, hostnames or SQL.
        return {"status": "ERROR", "reason": "BACKEND_UNAVAILABLE"}


@mcp.tool()
def search_public_notices(query: str, limit: int = 5) -> dict:
    """공개 공식 입찰공고 제목·기관·공고번호 검색 (최대 10건, 비공개 자료 제외)."""
    return _call(service.search_public_notices, query=query, limit=limit)


@mcp.tool()
def get_public_notice(notice_number: str) -> dict:
    """공식 입찰공고 1건의 공개 메타데이터 조회 (원문·개인자료 제외)."""
    return _call(service.get_public_notice, notice_number=notice_number)


@mcp.tool()
def search_public_rfp_passages(notice_number: str, query: str, limit: int = 5) -> dict:
    """공개·소유 없음·명시적 공유 승인이 모두 있는 현재 RFP의 근거 일부 검색 (기본 차단)."""
    return _call(service.search_public_rfp_passages, notice_number=notice_number, query=query, limit=limit)


def main() -> None:
    require_enabled()
    if os.environ.get("DJANGO_SETTINGS_MODULE") != "bid_server.settings.base":
        raise RuntimeError("MCP_SETTINGS_NOT_APPROVED")
    import django
    django.setup()
    # stdio process is only a local launcher boundary. Never start HTTP without OAuth/resource policy.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
