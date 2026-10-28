import json
from pathlib import Path
import sys

import pytest

from backend.agent.gateway_client import REVIEW_TOOL_NAMES
from backend.agent.reader import TOOL_NAMES
from scripts.run_campaign_agent import build_command


@pytest.fixture
def launch_fixture(tmp_path):
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "fixture.db").touch()
    (tmp_path / "private").mkdir()
    binding = tmp_path / "binding.json"
    binding.write_text(
        json.dumps(
            {
                "format": "dma-agent-binding-v1",
                "binding_id": "fixture-launch",
                "campaign_id": "fixture-launch",
                "recovery_epoch": "epoch-1",
                "role": "gm",
                "schema_revision": "20261028_0007",
                "database": "fixture.db",
                "private_root": "private",
            }
        )
    )
    workspace = tmp_path / "campaign-workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_bytes(
        (root / "agent/campaign-review-agent.md").read_bytes()
    )
    config = tmp_path / "config.toml"
    config.write_text(
        'sandbox_mode="read-only"\nweb_search="disabled"\n[mcp_servers.dma_campaign]\n'
        + "command="
        + json.dumps(Path(sys.executable).as_posix())
        + "\n"
        + "args="
        + json.dumps(
            [
                "-m",
                "backend.agent.mcp_server",
                "--binding",
                binding.as_posix(),
                "--operator-python",
                Path(sys.executable).as_posix(),
            ]
        )
        + "\n"
        + "cwd="
        + json.dumps(root.as_posix())
        + "\n"
        + "enabled_tools="
        + json.dumps(list(TOOL_NAMES + REVIEW_TOOL_NAMES))
        + "\nrequired=true\n"
    )
    (tmp_path / "agent-onboarding.json").write_text(
        json.dumps(
            {
                "fixture_only": True,
                "binding_file": str(binding),
                "agent_workspace": str(workspace),
                "config_template": str(config),
            }
        )
    )
    return binding, config, workspace


def test_launcher_ignores_inherited_tools_and_never_bypasses_sandbox(launch_fixture):
    binding, _, _ = launch_fixture
    command = build_command(binding, sys.executable)
    assert "--ignore-user-config" in command and "--ephemeral" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert not any("bypass" in value for value in command)
    overrides = {
        item.split("=", 1)[0]: json.loads(item.split("=", 1)[1])
        for index, item in enumerate(command)
        if index > 0 and command[index - 1] == "-c"
    }
    for field in (
        "shell_tool",
        "apps",
        "plugins",
        "multi_agent",
        "memories",
        "browser_use",
    ):
        assert overrides["features." + field] is False
    assert overrides["approval_policy"] == "never"
    assert (
        overrides["mcp_servers.dma_campaign.tools.review_execute.approval_mode"]
        == "approve"
    )
    assert not any(
        "grant" in name for name in overrides["mcp_servers.dma_campaign.enabled_tools"]
    )


@pytest.mark.parametrize(
    "damage",
    ["extra_tool", "extra_server", "sandbox", "notify", "transport", "instructions"],
)
def test_launcher_rejects_broadened_or_changed_profiles(launch_fixture, damage):
    binding, config, workspace = launch_fixture
    text = config.read_text()
    if damage == "extra_tool":
        text = text.replace('"review_execute"', '"review_execute", "approve"')
    elif damage == "extra_server":
        text += '\n[mcp_servers.other]\ncommand="elsewhere"\n'
    elif damage == "sandbox":
        text = text.replace(
            'sandbox_mode="read-only"', 'sandbox_mode="workspace-write"'
        )
    elif damage == "notify":
        text = 'notify=["unexpected-command"]\n' + text
    elif damage == "transport":
        text += '\n[mcp_servers.dma_campaign.tools.review_propose]\napproval_mode="approve"\n'
    else:
        (workspace / "AGENTS.md").write_text("Changed campaign instructions")
    config.write_text(text)
    with pytest.raises(ValueError):
        build_command(binding, sys.executable)
