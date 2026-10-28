"""Stdlib-only fixed backend bridge; never run model-supplied commands or paths."""

import asyncio
import json
from pathlib import Path

from backend.agent.reader import AgentReadError

REVIEW_TOOL_NAMES = (
    "session_stage_update",
    "review_propose",
    "review_receipt",
    "review_execute",
)


class GatewayClient:
    def __init__(self, backend_python: Path, binding_file: Path):
        self.backend_python = backend_python.resolve()
        self.binding_file = binding_file.resolve()
        self.root = Path(__file__).resolve().parents[2]
        if not self.backend_python.is_file():
            raise AgentReadError(
                "gateway_unavailable", "Select an installed backend Python"
            )

    async def health(self):
        return await self._exchange({"command": "health", "arguments": {}})

    async def call(self, name, arguments):
        if name not in REVIEW_TOOL_NAMES or not isinstance(arguments, dict):
            raise AgentReadError(
                "tool_unavailable", "This review capability is unavailable"
            )
        if name == "session_stage_update":
            payload = {
                "command": "propose",
                "arguments": {"request": {"operation": "stage_update", **arguments}},
            }
            if "operation" in arguments:
                raise AgentReadError(
                    "invalid_arguments", "Stage operation cannot be overridden"
                )
        elif name == "review_propose":
            payload = {"command": "propose", "arguments": {"request": arguments}}
        else:
            payload = {
                "command": "inspect" if name == "review_receipt" else "execute",
                "arguments": arguments,
            }
        return await self._exchange(payload)

    async def _exchange(self, payload):
        raw = json.dumps(payload).encode()
        if len(raw) > 150_000:
            raise AgentReadError(
                "invalid_arguments", "Review input exceeds the size limit"
            )
        process = await asyncio.create_subprocess_exec(
            str(self.backend_python),
            "-m",
            "scripts.campaign_agent_gateway",
            "--binding",
            str(self.binding_file),
            cwd=str(self.root),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(raw), timeout=25)
        except (asyncio.TimeoutError, asyncio.CancelledError) as exc:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.wait()
            if isinstance(exc, asyncio.CancelledError):
                raise
            raise AgentReadError(
                "gateway_unconfirmed",
                "No confirmed result; inspect the receipt before retrying",
            ) from None
        if process.returncode or len(stdout) > 1_000_000:
            raise AgentReadError(
                "gateway_unavailable", "Backend review result is unavailable"
            )
        try:
            result = json.loads(stdout)
            if result.get("ok") is not True:
                raise AgentReadError(
                    "review_denied", result.get("error", "Review request denied")
                )
            return result["data"]
        except (ValueError, KeyError, AttributeError):
            raise AgentReadError(
                "gateway_unavailable", "Backend review result is invalid"
            ) from None
