import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import sqlite3
import pytest

from backend.agent.reader import CampaignReader, TOOL_NAMES
from backend.agent.gateway_client import REVIEW_TOOL_NAMES


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("review_tools", [False, True])
def test_fixture_onboarding_uses_generated_sources_and_explicit_host_template(
    tmp_path, review_tools
):
    output = tmp_path / "agent-fixture"
    sentinel_db = tmp_path / "do-not-open.db"
    sentinel_overlay = tmp_path / "do-not-open-overlay"
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+aiosqlite:///" + sentinel_db.as_posix()
    env["DMA_PRIVATE_DATA_ROOT"] = str(sentinel_overlay)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.prepare_campaign_agent_fixture",
            "--workspace",
            str(output),
            "--agent-python",
            sys.executable,
        ]
        + (["--review-tools"] if review_tools else []),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout)
    assert report["fixture_only"] is True
    assert report["mutations_enabled"] is review_tools
    reader = CampaignReader(Path(report["binding_file"]))
    links = reader.call("campaign_read_sessions")["data"]
    draft = reader.call("session_read_review", {"draft_id": links[0]["draft_ids"][0]})
    assert draft["data"][0]["session_log_document_id"] in links[0]["log_document_ids"]
    assert draft["data"][0]["session_log_decision"] == "approved"
    notes = reader.call(
        "campaign_read_notes",
        {"note_type": "session", "item_id": links[0]["overlay_session_id"]},
    )
    assert notes["status"] == "ok"
    workspace = Path(report["agent_workspace"])
    assert (workspace / "AGENTS.md").read_bytes() == (
        ROOT
        / (
            "agent/campaign-review-agent.md"
            if review_tools
            else "agent/campaign-agent.md"
        )
    ).read_bytes()
    config = tomllib.loads(Path(report["config_template"]).read_text(encoding="utf-8"))
    assert config["sandbox_mode"] == "read-only"
    assert config["features"]["shell_tool"] is False
    assert config["web_search"] == "disabled"
    server = config["mcp_servers"]["dma_campaign"]
    assert set(server["enabled_tools"]) == set(
        TOOL_NAMES + (REVIEW_TOOL_NAMES if review_tools else ())
    )
    assert server["required"] is True
    assert (
        server["args"][server["args"].index("--binding") + 1]
        == Path(report["binding_file"]).as_posix()
    )
    assert not (workspace / ".codex/config.toml").exists()
    assert not sentinel_db.exists()
    assert not sentinel_overlay.exists()
    if review_tools:
        assert server["tools"] == {"review_execute": {"approval_mode": "approve"}}
        operator = [
            sys.executable,
            "-m",
            "scripts.review_campaign_approval",
            "--binding",
            report["binding_file"],
        ]

        def call(arguments, **kwargs):
            return subprocess.run(
                operator + arguments,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=40,
                **kwargs
            )

        proposed = call(["propose", "--request", report["operator_review_request"]])
        assert proposed.returncode == 0, proposed.stderr
        receipt = json.loads(proposed.stdout)
        assert receipt["status"] == "pending"
        piped = call(
            ["approve", "--approval-id", receipt["approval_id"]],
            input="APPROVE " + receipt["intent_hash"] + "\n",
        )
        assert piped.returncode == 2 and "interactive" in piped.stderr
        assert (
            call(["execute", "--approval-id", receipt["approval_id"]]).returncode == 2
        )
        shown = call(["show", "--approval-id", receipt["approval_id"]])
        assert json.loads(shown.stdout)["status"] == "pending"
        gateway = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.campaign_agent_gateway",
                "--binding",
                report["binding_file"],
            ],
            cwd=ROOT,
            env=env,
            input=json.dumps(
                {
                    "command": "approve",
                    "arguments": {"approval_id": receipt["approval_id"]},
                }
            ),
            capture_output=True,
            text=True,
            timeout=40,
        )
        assert json.loads(gateway.stdout)["ok"] is False
        with sqlite3.connect(reader.binding.database) as db:
            assert (
                db.execute("SELECT status FROM campaign_approvals").fetchone()[0]
                == "pending"
            )
