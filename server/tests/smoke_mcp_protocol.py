"""MCP SDK 2.3.0 메모리 프로토콜 스모크.

서버·실제 DB·외부 모델에 연결하지 않는 테스트: 도구 등록, 입력, OFF 경계 확인.
"""
import asyncio
import json
import os
from unittest.mock import patch

from mcp import Client
from bid_mcp.server import mcp
from bid_mcp import service


def payload(result):
    # MCP SDK 2.3.0 may return an object as text content, not structured_content.
    if result.structured_content is not None:
        return result.structured_content
    assert result.content and result.content[0].type == "text", result
    return json.loads(result.content[0].text)


async def main():
    async with Client(mcp) as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        expected = {"search_public_notices", "get_public_notice", "search_public_rfp_passages"}
        assert names == expected, names
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(service, "search_public_notices") as fake:
                result = await client.call_tool("search_public_notices", {"query": "AI", "limit": 2})
                assert payload(result)["reason"] == "MCP_DISABLED", result
                fake.assert_not_called()
        with patch.dict(os.environ, {"BID_MCP_ENABLED": "1", "BID_MCP_PUBLIC_ONLY": "1"}, clear=True):
            with patch.object(service, "search_public_notices", return_value={
                "status": "OK", "source": "G2B_OFFICIAL_API", "items": [],
            }) as fake:
                result = await client.call_tool("search_public_notices", {"query": "정보보안", "limit": 2})
                assert payload(result)["source"] == "G2B_OFFICIAL_API", result
                fake.assert_called_once_with(query="정보보안", limit=2)
            result = await client.call_tool("get_public_notice", {"notice_number": "../etc/passwd"})
            assert payload(result)["reason"] == "INVALID_NOTICE_NUMBER", result
    print("MCP_SDK_PROTOCOL_SMOKE_PASS tools=3 backend_calls_disabled=0", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
