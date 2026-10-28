"""Serve only a verified local rehearsal copy. External source fetching disabled."""

import argparse
import json
import os
from pathlib import Path
import socket

from scripts.review_campaign_approval import fixture_binding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    binding = fixture_binding(args.binding)
    root = args.binding.resolve().parent
    onboarding = json.loads(
        (root / "agent-onboarding.json").read_text(encoding="utf-8")
    )
    if onboarding.get("mode") != "private-rehearsal":
        raise ValueError("Select an explicitly verified private rehearsal")
    private = binding.private_root
    os.environ.update(
        {
            "DATABASE_URL": "sqlite+aiosqlite:///" + binding.database.as_posix(),
            "DMA_PRIVATE_DATA_ROOT": str(private),
            "DMA_CAMPAIGN_ID": binding.campaign_id,
            "DUNGEON_MAP_ROOT": str(private / "media"),
            "DUNGEON_ROOM_KEY_ROOT": str(private / "room-keys"),
            "REFERENCE_PDF_ROOT": str(private / "reference/raw"),
            "OBSIDIAN_VAULT_PATH": str(root / "legacy-disabled"),
            "EMBEDDING_PROVIDER": "disabled",
            "APP_ENV": "rehearsal",
            "DEBUG": "false",
            "LOG_LEVEL": "WARNING",
            "DMA_SESSION_NOTE_PATH": onboarding["session_path"],
            "DMA_INITIAL_MAP_ID": onboarding["map_id"],
            "MAPTOOL_BASE_URL": "http://127.0.0.1:9",
        }
    )
    from backend.api.main import app

    @app.middleware("http")
    async def local_only_browser(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; connect-src 'self'; frame-src 'self'"
        )
        return response

    import backend.services.aon_creature_service as aon

    def disabled(*args, **kwargs):
        raise RuntimeError(
            "External reference fetching disabled for this rehearsal; use local cached material"
        )

    aon.urlopen = disabled
    import uvicorn

    sock = socket.socket()
    sock.bind(("127.0.0.1", args.port))
    sock.listen(128)
    url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    (root / "server.json").write_text(
        json.dumps({"url": url, "mode": "private-rehearsal"}), encoding="utf-8"
    )
    print("PRIVATE_REHEARSAL=" + url, flush=True)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


if __name__ == "__main__":
    main()
