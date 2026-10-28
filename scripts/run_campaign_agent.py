"""Launch a dedicated fixture campaign conversation without development tools.

Uses the installed Codex CLI's normal authentication, ignores user MCP/config
inheritance, and passes the generated restricted profile as per-run overrides.
No credentials or global configuration are copied or changed.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

from backend.agent.gateway_client import REVIEW_TOOL_NAMES
from backend.agent.reader import TOOL_NAMES
from scripts.review_campaign_approval import fixture_binding


DISABLED_FEATURES = (
    "shell_tool",
    "apps",
    "plugins",
    "multi_agent",
    "multi_agent_v2",
    "memories",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "view_image",
    "workspace_dependencies",
    "skill_search",
    "sleep_tool",
    "tool_suggest",
)


def build_command(binding_file: Path, codex: str):
    fixture_binding(binding_file)
    root = binding_file.resolve().parent
    onboarding = json.loads(
        (root / "agent-onboarding.json").read_text(encoding="utf-8")
    )
    config_path = Path(onboarding["config_template"]).resolve()
    workspace = Path(onboarding["agent_workspace"]).resolve()
    if not config_path.is_relative_to(root) or not workspace.is_relative_to(root):
        raise ValueError("Dedicated profile must stay inside its generated fixture")
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if set(config) - {
        "sandbox_mode",
        "web_search",
        "features",
        "agents",
        "mcp_servers",
    }:
        raise ValueError("Unexpected host configuration fields")
    server = config.get("mcp_servers", {}).get("dma_campaign", {})
    if set(config.get("mcp_servers", {})) != {"dma_campaign"} or set(
        server.get("enabled_tools", [])
    ) != set(TOOL_NAMES + REVIEW_TOOL_NAMES):
        raise ValueError(
            "A dedicated W1 review profile with exactly twelve tools is required"
        )
    if (
        config.get("sandbox_mode") != "read-only"
        or config.get("web_search") != "disabled"
    ):
        raise ValueError(
            "Dedicated host requires a read-only filesystem and disabled search"
        )
    allowed_server = {
        "command",
        "args",
        "cwd",
        "enabled_tools",
        "required",
        "startup_timeout_sec",
        "tool_timeout_sec",
        "tools",
    }
    if set(server) - allowed_server or server.get("required") is not True:
        raise ValueError("Unexpected MCP process configuration")
    if server.get("tools", {}) not in (
        {},
        {"review_execute": {"approval_mode": "approve"}},
    ):
        raise ValueError(
            "Only the independently guarded receipt endpoint can have a transport approval override"
        )
    repository = Path(__file__).resolve().parents[1]
    if Path(server.get("cwd", "")).resolve() != repository:
        raise ValueError("MCP process must use the checked repository implementation")
    expected = [
        "-m",
        "backend.agent.mcp_server",
        "--binding",
        binding_file.resolve().as_posix(),
        "--operator-python",
    ]
    if server.get("args", [])[:5] != expected or len(server["args"]) != 6:
        raise ValueError("Unexpected MCP launcher arguments")
    profile = (workspace / "AGENTS.md").read_text(encoding="utf-8")
    if profile != (repository / "agent/campaign-review-agent.md").read_text(
        encoding="utf-8"
    ):
        raise ValueError(
            "Campaign instructions changed; regenerate/review the dedicated profile"
        )
    executable = shutil.which(codex)
    if not executable:
        raise ValueError("Select the installed Codex CLI with --codex")
    command = [
        executable,
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--cd",
        str(workspace),
        "--json",
        "--color",
        "never",
    ]
    overrides = {
        "web_search": "disabled",
        "approval_policy": "never",
        "agents.enabled": False,
        "project_doc_max_bytes": 0,
        "developer_instructions": profile,
        "features.code_mode_host": True,
        "features.shell_snapshot": False,
        "apps._default.enabled": False,
        **{"features." + name: False for name in DISABLED_FEATURES},
        **{
            "mcp_servers.dma_campaign." + key: value
            for key, value in server.items()
            if key != "tools"
        },
        "mcp_servers.dma_campaign.tools.review_execute.approval_mode": "approve",
    }
    for key, value in overrides.items():
        command.extend(["-c", key + "=" + json.dumps(value, ensure_ascii=True)])
    return command


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--events", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full event JSON instead of the campaign answer",
    )
    args = parser.parse_args()
    try:
        if args.events and args.events.exists():
            raise ValueError("Choose a new event evidence file")
        command = build_command(args.binding, args.codex)
        result = subprocess.run(
            command + ["-"],
            input=args.prompt,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=300,
        )
        if args.events:
            with args.events.open("x", encoding="utf-8") as handle:
                handle.write(result.stdout)
        if args.json:
            print(result.stdout, end="")
        else:
            messages = []
            for line in result.stdout.splitlines():
                try:
                    item = json.loads(line).get("item", {})
                    if item.get("type") == "agent_message":
                        messages.append(item["text"])
                except (ValueError, KeyError, AttributeError):
                    continue
            if messages:
                print(messages[-1])
            elif result.returncode == 0:
                raise ValueError(
                    "The campaign host returned no final answer; inspect the event evidence"
                )
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
