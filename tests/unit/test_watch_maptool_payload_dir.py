import json

import httpx

from scripts.watch_maptool_payload_dir import main

REAL_HTTPX_CLIENT = httpx.Client


def test_watch_maptool_payload_dir_processes_json_once(monkeypatch, tmp_path, capsys):
    payload_dir = tmp_path / "exports"
    payload_dir.mkdir()
    (payload_dir / "map-state.json").write_text(
        json.dumps({"id": "demo-map", "name": "Demo", "tokens": []}),
        encoding="utf-8",
    )

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"id": "demo-map", "name": "Demo"})

    transport = httpx.MockTransport(handler)

    class MockClient:
        def __init__(self, base_url: str, timeout: float):
            self._client = REAL_HTTPX_CLIENT(
                transport=transport,
                base_url=base_url,
                timeout=timeout,
            )

        def __enter__(self):
            return self._client

        def __exit__(self, exc_type, exc, tb):
            self._client.close()
            return False

    monkeypatch.setattr("scripts.push_maptool_payload_file.httpx.Client", MockClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "watch_maptool_payload_dir.py",
            "--dir",
            str(payload_dir),
            "--bridge-url",
            "http://127.0.0.1:5005",
            "--once",
        ],
    )

    assert main() == 0
    output = capsys.readouterr().out

    assert captured["url"] == "http://127.0.0.1:5005/bridge/map-state"
    assert "Pushed" in output
