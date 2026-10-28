"""Operator-only approval console, initially restricted to generated W1 fixtures.

Uses the backend Python, never the isolated MCP environment. No live paths or
default .env database are selected automatically. There is no --yes option.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from backend.agent.reader import AgentReadError, CampaignBinding


def fixture_binding(path: Path):
    path = path.resolve()
    binding = CampaignBinding.load(path)
    try:
        onboarding = json.loads(
            (path.parent / "agent-onboarding.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise ValueError(
            "Select a generated agent fixture with its onboarding record"
        ) from exc
    if (
        onboarding.get("fixture_only") is not True
        or Path(onboarding.get("binding_file", "")).resolve() != path
        or not binding.binding_id.startswith("fixture-")
        or not binding.database.is_relative_to(path.parent)
        or not binding.private_root.is_relative_to(path.parent)
    ):
        raise ValueError("This console is restricted to a generated disposable fixture")
    return binding


def confirm_review(view, *, source=None, destination=None) -> bool:
    source = source or sys.stdin
    destination = destination or sys.stdout
    if not source.isatty():
        raise ValueError(
            "Approval requires an interactive operator terminal; piped approval is disabled"
        )
    # JSON escaping prevents control sequences in untrusted source notes from
    # changing the display or disguising the confirmation prompt.
    destination.write(json.dumps(view, indent=2, ensure_ascii=True) + "\n")
    destination.write(
        "Approve only this displayed operation. Type APPROVE "
        + view["intent_hash"]
        + ":\n"
    )
    destination.flush()
    return source.readline().strip() == "APPROVE " + view["intent_hash"]


async def run(args):
    binding = fixture_binding(args.binding)
    # Configure the fresh backend process before importing application settings.
    if "backend.config.settings" in sys.modules:
        raise ValueError("Run the approval console in a fresh backend Python process")
    from sqlalchemy.engine import URL

    os.environ["DATABASE_URL"] = URL.create(
        "sqlite+aiosqlite", database=str(binding.database)
    ).render_as_string(hide_password=False)
    os.environ["DMA_PRIVATE_DATA_ROOT"] = str(binding.private_root)
    os.environ["DMA_CAMPAIGN_ID"] = binding.campaign_id
    os.environ["EMBEDDING_PROVIDER"] = "disabled"
    from backend.agent.approvals import ApprovalWorkflow

    workflow = ApprovalWorkflow(args.binding)
    try:
        if args.action == "propose":
            with args.request.open("rb") as handle:
                content = handle.read(100_001)
            if len(content) > 100_000:
                raise ValueError("Review request exceeds the input size limit")
            result = await workflow.propose(json.loads(content))
        elif args.action == "show":
            result = await workflow.inspect(args.approval_id)
        elif args.action == "approve":
            view = await workflow.inspect(args.approval_id)
            if not confirm_review(view):
                raise ValueError("Approval cancelled; no approval was granted")
            result = await workflow.approve(
                args.approval_id, displayed_hash=view["intent_hash"]
            )
        elif args.action == "revoke":
            result = await workflow.revoke(args.approval_id)
        else:
            result = await workflow.execute(args.approval_id)
        print(json.dumps(result, indent=2, ensure_ascii=True))
    finally:
        await workflow.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    proposal = actions.add_parser("propose")
    proposal.add_argument("--request", type=Path, required=True)
    for name in ("show", "approve", "execute", "revoke"):
        command = actions.add_parser(name)
        command.add_argument("--approval-id", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (AgentReadError, ValueError, LookupError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception:
        print(
            "No confirmed result returned; inspect the receipt before retrying.",
            file=sys.stderr,
        )
        raise SystemExit(3) from None


if __name__ == "__main__":
    main()
