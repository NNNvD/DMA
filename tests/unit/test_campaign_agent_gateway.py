import asyncio
import json
from pathlib import Path
import sys

import pytest

from backend.agent.gateway_client import GatewayClient
from backend.agent.reader import AgentReadError


@pytest.mark.parametrize(
    "outcome", ["ok", "invalid", "denied", "timeout", "cancelled", "failed"]
)
def test_fixed_gateway_transport_and_uncertain_execution_handling(
    tmp_path, monkeypatch, outcome
):
    calls = []

    class Process:
        returncode = None
        killed = False
        waited = False

        async def communicate(self, raw):
            calls.append(json.loads(raw))
            if outcome == "timeout":
                raise asyncio.TimeoutError()
            if outcome == "cancelled":
                raise asyncio.CancelledError()
            self.returncode = 1 if outcome == "failed" else 0
            if outcome == "invalid":
                return b"not-json", b"private diagnostics"
            if outcome == "denied":
                return (
                    json.dumps(
                        {"ok": False, "error": "operator did not approve"}
                    ).encode(),
                    b"",
                )
            return json.dumps({"ok": True, "data": {"replayed": False}}).encode(), b""

        def kill(self):
            self.killed = True

        async def wait(self):
            self.waited = True
            self.returncode = 1

    process = Process()

    async def spawn(*args, **kwargs):
        calls.append(args)
        assert kwargs["stdin"] == asyncio.subprocess.PIPE
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    client = GatewayClient(Path(sys.executable), tmp_path / "binding.json")
    if outcome == "ok":
        assert asyncio.run(
            client.call("review_execute", {"approval_id": "receipt"})
        ) == {"replayed": False}
    else:
        error = asyncio.CancelledError if outcome == "cancelled" else AgentReadError
        with pytest.raises(error):
            asyncio.run(client.call("review_execute", {"approval_id": "receipt"}))
    assert calls[0][1:3] == ("-m", "scripts.campaign_agent_gateway")
    assert calls[1] == {"command": "execute", "arguments": {"approval_id": "receipt"}}
    if outcome in {"timeout", "cancelled"}:
        assert process.killed and process.waited


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("approve", {}),
        ("shell", {}),
        ("health", {}),
        ("session_stage_update", {"operation": "approve"}),
    ],
)
def test_unexported_gateway_capabilities_never_start_backend(
    tmp_path, monkeypatch, name, arguments
):
    async def forbidden(*args, **kwargs):
        pytest.fail("Unavailable capabilities must not start a backend process")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    client = GatewayClient(Path(sys.executable), tmp_path / "binding.json")
    with pytest.raises(AgentReadError):
        asyncio.run(client.call(name, arguments))
