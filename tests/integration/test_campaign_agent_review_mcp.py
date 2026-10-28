"""Real SDK and isolated backend processes; operator grants are fixture simulation."""

import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from backend.agent.gateway_client import REVIEW_TOOL_NAMES
from backend.agent.reader import TOOL_NAMES

mcp = pytest.importorskip("mcp", reason="Use the isolated agent environment")
stdio_client = pytest.importorskip("mcp.client.stdio").stdio_client
ROOT = Path(__file__).resolve().parents[2]


def test_guarded_mcp_stage_review_and_fresh_session_resume(tmp_path):
    supplied = os.environ.get("DMA_W1_FIXTURE_BINDING")
    backend = os.environ.get("DMA_TEST_BACKEND_PYTHON")
    if not supplied or not backend:
        pytest.skip(
            "Set DMA_W1_FIXTURE_BINDING to a generated --review-tools fixture and DMA_TEST_BACKEND_PYTHON"
        )
    workspace = tmp_path / "fixture"
    shutil.copytree(Path(supplied).resolve().parent, workspace)
    binding = workspace / "binding.json"
    onboarding = json.loads(
        (workspace / "agent-onboarding.json").read_text(encoding="utf-8")
    )
    onboarding["binding_file"] = str(binding)
    (workspace / "agent-onboarding.json").write_text(
        json.dumps(onboarding), encoding="utf-8"
    )
    params = mcp.StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "backend.agent.mcp_server",
            "--binding",
            str(binding),
            "--operator-python",
            backend,
        ],
        cwd=str(ROOT),
    )
    stage = {
        "session_id": "fixture-review-session",
        "request_key": "sdk-w1-stage-1",
        "title": "Fictional W1 bridge record",
        "content": "## NPC: Fixture W1 Scholar\nSummary: Confirmed fictional scholar\n",
        "source_name": "Fictional SDK test DM message",
        "source_refs": ["dm-message://fixture/sdk-1"],
    }

    def payload(result):
        assert not result.isError, result
        return result.structuredContent or json.loads(result.content[0].text)

    def approve_fixture(receipt, expected_request):
        # This trusted test driver is outside the MCP agent. No approve gateway
        # command is added for this simulation and no real campaign is accepted.
        code = """import asyncio,json,sys
from pathlib import Path
from scripts.review_campaign_approval import fixture_binding
fixture_binding(Path(sys.argv[1]))
from backend.agent.approvals import ApprovalWorkflow
async def main():
 w=ApprovalWorkflow(Path(sys.argv[1]))
 try:
  v=await w.inspect(sys.argv[2])
  assert v['intent']['request']==json.loads(sys.argv[3])
  await w.approve(sys.argv[2],displayed_hash=v['intent_hash'])
 finally: await w.close()
asyncio.run(main())
"""
        completed = subprocess.run(
            [
                backend,
                "-c",
                code,
                str(binding),
                receipt["approval_id"],
                json.dumps(expected_request),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=40,
            env={**os.environ, "EMBEDDING_PROVIDER": "disabled"},
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr

    async def conversation(action):
        async with stdio_client(params) as (read, write):
            async with mcp.ClientSession(
                read, write, read_timeout_seconds=timedelta(seconds=40)
            ) as session:
                await session.initialize()
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert names == set(TOOL_NAMES + REVIEW_TOOL_NAMES)
                assert not any("approve" in name or "shell" in name for name in names)
                return await action(session)

    async def initial(session):
        description = payload(await session.call_tool("campaign_describe", {}))
        assert description["data"]["operator_approval_required"] is True
        before = payload(await session.call_tool("session_read_review", {}))
        receipt = payload(await session.call_tool("session_stage_update", stage))
        assert receipt["status"] == "pending"
        assert (
            await session.call_tool(
                "review_execute", {"approval_id": receipt["approval_id"]}
            )
        ).isError
        assert (
            await session.call_tool("approve", {"approval_id": receipt["approval_id"]})
        ).isError
        assert payload(await session.call_tool("session_read_review", {})) == before
        assert (
            payload(await session.call_tool("session_stage_update", stage))[
                "approval_id"
            ]
            == receipt["approval_id"]
        )
        return receipt

    receipt = asyncio.run(conversation(initial))
    approve_fixture(receipt, {"operation": "stage_update", **stage})

    async def stage_and_review(session):
        staged = payload(
            await session.call_tool(
                "review_execute", {"approval_id": receipt["approval_id"]}
            )
        )["result"]
        draft_id = staged["id"]
        saved = payload(
            await session.call_tool(
                "campaign_read_sessions", {"session_id": stage["session_id"]}
            )
        )
        assert draft_id in saved["data"][0]["draft_ids"]
        assert any(ref["store"] == "sql" for ref in saved["sources"])
        current = payload(
            await session.call_tool("session_read_review", {"draft_id": draft_id})
        )["data"][0]
        assert current["decisions"] == {} and current["status"] == "pending"
        req = {
            "operation": "decide_candidate",
            "draft_id": draft_id,
            "expected_revision": current["revision"],
            "session_id": stage["session_id"],
            "candidate_id": current["candidates"][0]["id"],
            "decision": "accepted",
        }
        candidate = payload(await session.call_tool("review_propose", req))
        approve_fixture(candidate, req)
        decision = payload(
            await session.call_tool(
                "review_execute", {"approval_id": candidate["approval_id"]}
            )
        )["result"]
        req = {
            "operation": "promote",
            "draft_id": draft_id,
            "expected_revision": decision["draft_revision"],
            "session_id": stage["session_id"],
        }
        promote = payload(await session.call_tool("review_propose", req))
        approve_fixture(promote, req)
        promoted = payload(
            await session.call_tool(
                "review_execute", {"approval_id": promote["approval_id"]}
            )
        )["result"]
        entity_id = promoted["decisions"][current["candidates"][0]["id"]]["promotion"][
            "entity_id"
        ]
        req = {
            "operation": "finalize_log",
            "draft_id": draft_id,
            "expected_revision": promoted["revision"],
            "session_id": stage["session_id"],
            "decision": "approved",
        }
        final = payload(await session.call_tool("review_propose", req))
        approve_fixture(final, req)
        finalized = payload(
            await session.call_tool(
                "review_execute", {"approval_id": final["approval_id"]}
            )
        )["result"]
        history = payload(
            await session.call_tool(
                "campaign_read_history",
                {"document_id": finalized["session_log_document_id"]},
            )
        )
        assert history["data"][0]["title"] == stage["title"]
        return (
            draft_id,
            entity_id,
            finalized["session_log_document_id"],
            history["sources"][0]["citation"],
        )

    draft_id, entity_id, log_id, citation = asyncio.run(conversation(stage_and_review))

    async def resume(session):
        saved = payload(
            await session.call_tool(
                "campaign_read_sessions", {"session_id": stage["session_id"]}
            )
        )
        assert draft_id in saved["data"][0]["draft_ids"]
        history = payload(
            await session.call_tool("campaign_read_history", {"document_id": log_id})
        )
        assert history["sources"][0]["citation"] == citation
        provenance = payload(
            await session.call_tool(
                "campaign_read_provenance", {"entity_id": entity_id}
            )
        )
        assert provenance["data"][0]["draft_id"] == draft_id
        assert (
            payload(
                await session.call_tool(
                    "review_execute", {"approval_id": receipt["approval_id"]}
                )
            )["replayed"]
            is True
        )

    asyncio.run(conversation(resume))
