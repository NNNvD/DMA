"""Create a fictional W1 agent binding using the real W0 application fixture.

Uses the backend development Python. The MCP server uses its separate Python
environment supplied with --agent-python. No live source paths are accepted.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from uuid import uuid4

from backend.agent.reader import CampaignReader, TOOL_NAMES
from backend.agent.gateway_client import REVIEW_TOOL_NAMES
from scripts.rehearse_campaign_recovery import (
    OVERLAY_NAME,
    PRIVATE_CHILD,
    PROJECT_ROOT,
    run_rehearsal,
)


def prepare_fixture(
    workspace: Path, agent_python: Path, *, review_tools: bool = False
) -> dict:
    agent_python = agent_python.resolve()
    if not agent_python.is_file():
        raise ValueError("Select the installed isolated agent Python executable")
    # W0 refuses existing/protected targets and overrides all inherited live paths.
    recovery = run_rehearsal(workspace)
    workspace = Path(recovery["workspace"])
    database = workspace / "restored/database.sqlite3"
    private = workspace / "restored" / OVERLAY_NAME / PRIVATE_CHILD
    identity = {
        "binding_id": "fixture-" + uuid4().hex,
        "campaign_id": recovery["identity"]["campaign_id"],
        "role": "gm",
        "recovery_epoch": uuid4().hex,
    }
    with closing(sqlite3.connect(database)) as db:
        approved = db.execute(
            "SELECT id,session_log_document_id FROM session_update_drafts WHERE session_log_decision='approved' AND status='finalized'"
        ).fetchall()
        if len(approved) != 1:
            raise ValueError("Expected one explicitly approved fictional session")
        pending = [
            row
            for row in db.execute(
                "SELECT id,revision,candidates,decisions FROM session_update_drafts WHERE status='pending'"
            ).fetchall()
            if json.loads(row[3]) == {} and json.loads(row[2])
        ]
        if len(pending) != 1:
            raise ValueError("Expected one undecided fictional review source")
        db.execute(
            "INSERT INTO contexts (key,data,revision,updated_at) VALUES (?,?,?,?)",
            (
                "campaign-agent-binding",
                json.dumps(identity),
                1,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()
    (private / ".dma-agent-binding.json").write_text(
        json.dumps(identity, indent=2), encoding="utf-8"
    )
    links = {
        "campaign_id": identity["campaign_id"],
        "items": [
            {
                "id": recovery["identity"]["session_id"],
                "overlay_session_id": "fixture-session-1",
                "draft_ids": [approved[0][0]],
                "log_document_ids": [approved[0][1]],
            },
            {
                "id": "fixture-review-session",
                "draft_ids": [pending[0][0]],
                "log_document_ids": [],
            },
        ],
    }
    (
        private / "campaigns" / identity["campaign_id"] / "agent-session-links.json"
    ).write_text(json.dumps(links, indent=2), encoding="utf-8")
    binding = workspace / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "format": "dma-agent-binding-v1",
                **identity,
                "schema_revision": recovery["schema_revision"],
                "database": database.relative_to(workspace).as_posix(),
                "private_root": private.relative_to(workspace).as_posix(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    review_request = workspace / "operator-review-request.json"
    review_request.write_text(
        json.dumps(
            {
                "operation": "decide_candidate",
                "draft_id": pending[0][0],
                "expected_revision": pending[0][1],
                "session_id": "fixture-review-session",
                "candidate_id": json.loads(pending[0][2])[0]["id"],
                "decision": "accepted",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    reader = CampaignReader(binding)
    description = reader.call("campaign_describe")
    if description["data"]["mutations_enabled"]:
        raise RuntimeError("Fixture must remain read-only")
    agent_workspace = workspace / "campaign-workspace"
    agent_workspace.mkdir()
    shutil.copyfile(
        PROJECT_ROOT
        / (
            "agent/campaign-review-agent.md"
            if review_tools
            else "agent/campaign-agent.md"
        ),
        agent_workspace / "AGENTS.md",
    )
    # This is a reviewable template, not an edit to user/project Codex settings.
    config = workspace / "codex-config.example.toml"
    config.write_text(
        'sandbox_mode = "read-only"\nweb_search = "disabled"\n\n[features]\nshell_tool = false\napps = false\nplugins = false\nmulti_agent = false\nmemories = false\nbrowser_use = false\nview_image = false\nworkspace_dependencies = false\n\n[agents]\nenabled = false\n\n'
        "[mcp_servers.dma_campaign]\n"
        + "command = "
        + json.dumps(agent_python.as_posix())
        + "\n"
        + "args = "
        + json.dumps(
            ["-m", "backend.agent.mcp_server", "--binding", binding.as_posix()]
            + (
                ["--operator-python", Path(sys.executable).as_posix()]
                if review_tools
                else []
            )
        )
        + "\n"
        + "cwd = "
        + json.dumps(PROJECT_ROOT.as_posix())
        + "\n"
        + "enabled_tools = "
        + json.dumps(
            list(TOOL_NAMES) + (list(REVIEW_TOOL_NAMES) if review_tools else [])
        )
        + "\n"
        + "required = true\nstartup_timeout_sec = 20\n"
        + ("tool_timeout_sec = 40\n" if review_tools else "tool_timeout_sec = 20\n")
        + (
            '\n[mcp_servers.dma_campaign.tools.review_execute]\napproval_mode = "approve"\n'
            if review_tools
            else ""
        ),
        encoding="utf-8",
    )
    result = {
        "fixture_only": True,
        "binding_file": str(binding),
        "agent_workspace": str(agent_workspace),
        "config_template": str(config),
        "mutations_enabled": review_tools,
        "operator_approval_required": review_tools,
        "operator_review_request": str(review_request),
    }
    (workspace / "agent-onboarding.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--agent-python", type=Path, required=True)
    parser.add_argument(
        "--review-tools",
        action="store_true",
        help="Enable fixture-bound request/receipt/approved-execution tools",
    )
    args = parser.parse_args()
    workspace = (
        args.workspace
        or Path(tempfile.mkdtemp(prefix="dma-agent-fixture-")) / "fixture"
    )
    print(
        json.dumps(
            prepare_fixture(
                workspace, args.agent_python, review_tools=args.review_tools
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
