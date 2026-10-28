import asyncio
from datetime import timedelta
import json
from pathlib import Path
import sys

import pytest

from backend.agent.reader import TOOL_NAMES
from tests.support.campaign_agent_fixtures import make_reader_fixture


mcp = pytest.importorskip(
    "mcp", reason="Run agent-test in the isolated requirements-agent-dev environment"
)
ClientSession, StdioServerParameters = mcp.ClientSession, mcp.StdioServerParameters
stdio_client = pytest.importorskip("mcp.client.stdio").stdio_client
ROOT = Path(__file__).resolve().parents[2]


def _payload(result):
    assert not result.isError, result
    return result.structuredContent or json.loads(result.content[0].text)


def test_sdk_stdio_connection_and_fresh_session_resume(tmp_path):
    binding, _, private = make_reader_fixture(tmp_path)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.agent.mcp_server", "--binding", str(binding)],
        cwd=str(ROOT),
    )

    async def connect():
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=20)
            ) as session:
                initialized = await session.initialize()
                assert "read-only W1 profile" in initialized.instructions
                listing = await session.list_tools()
                assert {t.name for t in listing.tools} == set(TOOL_NAMES)
                assert all(
                    t.annotations.readOnlyHint and not t.annotations.destructiveHint
                    for t in listing.tools
                )
                assert all(
                    t.inputSchema["additionalProperties"] is False
                    for t in listing.tools
                )
                resumed = await session.get_prompt("campaign_resume")
                assert "fresh conversation" in resumed.messages[0].content.text
                description = _payload(await session.call_tool("campaign_describe", {}))
                assert description["data"]["mutations_enabled"] is False
                links = _payload(
                    await session.call_tool(
                        "campaign_read_sessions", {"session_id": "session-1"}
                    )
                )
                assert links["data"][0]["id"] == "session-1"
                history = _payload(
                    await session.call_tool("campaign_read_history", {"document_id": 3})
                )
                assert history["data"][0]["id"] == 3
                notes = _payload(
                    await session.call_tool(
                        "campaign_read_notes",
                        {
                            "note_type": "session",
                            "item_id": links["data"][0]["overlay_session_id"],
                        },
                    )
                )
                assert (
                    notes["data"]["body_markdown"] == "Fictional GM-only bridge note."
                )
                entity = _payload(
                    await session.call_tool("campaign_read_entities", {"entity_id": 42})
                )
                assert (
                    await session.call_tool("review_promote", {"draft_id": 7})
                ).isError
                assert (
                    await session.call_tool(
                        "campaign_read_entities", {"database": "/another.db"}
                    )
                ).isError
                assert (
                    await session.call_tool(
                        "campaign_read_notes",
                        {"note_type": "../../.env", "item_id": "42"},
                    )
                ).isError
                return entity["sources"][0]["citation"]

    first = asyncio.run(connect())
    assert asyncio.run(connect()) == first
    marker_path = private / ".dma-agent-binding.json"
    marker = json.loads(marker_path.read_text())
    marker["recovery_epoch"] = "rotated"
    marker_path.write_text(json.dumps(marker))
    from backend.agent.reader import AgentReadError, CampaignReader

    with pytest.raises(AgentReadError):
        CampaignReader(binding)
