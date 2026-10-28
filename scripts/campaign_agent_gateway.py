"""Closed stdio bridge from the MCP environment to fixture-bound backend tools.

No approve/revoke command exists here. Human authority stays in the operator
console. A request can create a pending receipt, read it, or consume it only
after the operator has approved that exact intent.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from scripts.review_campaign_approval import fixture_binding


async def dispatch(binding_file, message):
    binding = fixture_binding(binding_file)
    if "backend.config.settings" in sys.modules:
        raise ValueError("Start the bound gateway in a fresh backend process")
    from sqlalchemy.engine import URL

    os.environ.update(
        {
            "DATABASE_URL": URL.create(
                "sqlite+aiosqlite", database=str(binding.database)
            ).render_as_string(hide_password=False),
            "DMA_PRIVATE_DATA_ROOT": str(binding.private_root),
            "DMA_CAMPAIGN_ID": binding.campaign_id,
            "EMBEDDING_PROVIDER": "disabled",
        }
    )
    from backend.agent.approvals import ApprovalWorkflow

    if (
        not isinstance(message, dict)
        or set(message) != {"command", "arguments"}
        or not isinstance(message["arguments"], dict)
    ):
        raise ValueError("Expected an exact gateway command and arguments")
    command, arguments = message["command"], message["arguments"]
    if command == "propose":
        if set(arguments) != {"request"}:
            raise ValueError("Proposal requires an exact review request")
    elif command == "health":
        if arguments:
            raise ValueError("Health check takes no model-selected arguments")
    elif command in {"inspect", "execute"}:
        if set(arguments) != {"approval_id"}:
            raise ValueError("An exact receipt ID is required")
    else:
        raise ValueError("This capability is unavailable to the campaign agent")
    workflow = ApprovalWorkflow(binding_file)
    try:
        if command == "health":
            from sqlalchemy import select
            from backend.models.campaign_approval import CampaignApproval

            async with workflow.sessions() as db:
                await db.execute(select(CampaignApproval.id).limit(1))
            return {"status": "ready", "operator_approval_required": True}
        if command == "propose":
            return await workflow.propose(arguments["request"])
        if command == "inspect":
            return await workflow.inspect(arguments["approval_id"])
        return await workflow.execute(arguments["approval_id"])
    finally:
        await workflow.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(150_001)
        if len(raw) > 150_000:
            raise ValueError("Gateway input exceeds the size limit")
        result = asyncio.run(dispatch(args.binding, json.loads(raw)))
        print(json.dumps({"ok": True, "data": result}, ensure_ascii=True))
    except (ValueError, LookupError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True))
    except Exception:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No confirmed result; inspect the receipt before retrying",
                }
            )
        )


if __name__ == "__main__":
    main()
