"""MCP 工具服务冒烟：装了 fastmcp 才跑。"""
import asyncio

import pytest

pytest.importorskip("fastmcp")

from ra.demo import build_dual  # noqa: E402
from ra.mcp_server import build_server  # noqa: E402

EXPECTED = ["search_regulation", "query_report_data", "generate_material"]


def test_tools_are_registered():
    server = build_server(build_dual())

    async def registered() -> list[str]:
        found = []
        for name in EXPECTED:
            if await server.get_tool(name):
                found.append(name)
        return found

    assert asyncio.run(registered()) == EXPECTED
