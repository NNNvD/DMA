"""Verify a bound reader over real MCP stdio, then reconnect with no chat history.

Run in the isolated agent environment. This reads the explicitly selected
binding; use a generated fixture until live-campaign access is approved.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from backend.agent.reader import TOOL_NAMES


ROOT = Path(__file__).resolve().parents[1]


def _payload(result) -> dict:
    if result.isError:
        raise RuntimeError("Bound campaign tool refused the verification request")
    return result.structuredContent or json.loads(result.content[0].text)


async def verify_connection(binding: Path) -> dict:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "backend.agent.mcp_server", "--binding", str(binding.resolve())],
        cwd=str(ROOT),
    )
    references = []
    identity = None
    for _ in range(2):
        async with stdio_client(params) as (read, write):
            async with ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=20)
            ) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                if {tool.name for tool in tools} != set(TOOL_NAMES) or not all(
                    tool.annotations and tool.annotations.readOnlyHint for tool in tools
                ):
                    raise RuntimeError("Unexpected or non-read-only tool registry")
                description = _payload(await client.call_tool("campaign_describe", {}))
                identity = {
                    key: description[key]
                    for key in ("binding_id", "campaign_id", "recovery_epoch", "role")
                }
                sessions = _payload(
                    await client.call_tool("campaign_read_sessions", {})
                )
                if not sessions["data"]:
                    raise RuntimeError(
                        "No saved session associations available for resume verification"
                    )
                entities = _payload(
                    await client.call_tool("campaign_read_entities", {"limit": 1})
                )
                history = _payload(
                    await client.call_tool("campaign_read_history", {"limit": 1})
                )
                live = _payload(await client.call_tool("session_read_live", {}))
                review = _payload(await client.call_tool("session_read_review", {}))
                if any(
                    payload["status"] != "ok"
                    for payload in (entities, history, live, review)
                ):
                    raise RuntimeError(
                        "Fixture must provide entities, history, live state and review records"
                    )
                selected = sessions["data"][0]
                note = _payload(
                    await client.call_tool(
                        "campaign_read_notes",
                        {
                            "note_type": "session",
                            "item_id": selected["overlay_session_id"],
                        },
                    )
                )
                if note["status"] != "ok":
                    raise RuntimeError(
                        "Saved overlay session reference does not resolve"
                    )
                references.append(
                    [
                        source["citation"]
                        for payload in (sessions, entities, history, live, review, note)
                        for source in payload["sources"]
                    ]
                )
                if not (
                    await client.call_tool("review_promote", {"draft_id": 1})
                ).isError:
                    raise RuntimeError("Unavailable mutation unexpectedly succeeded")
                if not (
                    await client.call_tool(
                        "campaign_read_entities", {"database": "outside-binding"}
                    )
                ).isError:
                    raise RuntimeError(
                        "Unsupported source override unexpectedly succeeded"
                    )
    if references[0] != references[1]:
        raise RuntimeError("Fresh server sessions returned different source references")
    return {
        "identity": identity,
        "tools": list(TOOL_NAMES),
        "fresh_sessions": 2,
        "source_references": references[0],
        "writes_denied": True,
        "scope_overrides_denied": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = asyncio.run(verify_connection(args.binding))
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8") as output:
            output.write(text)
    print(text)


if __name__ == "__main__":
    main()
