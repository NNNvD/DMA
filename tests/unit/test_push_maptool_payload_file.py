import json

import httpx

from scripts.push_maptool_payload_file import main

REAL_HTTPX_CLIENT = httpx.Client


def test_push_maptool_payload_file_posts_validated_payload(monkeypatch, tmp_path, capsys):
    payload_path = tmp_path / "map-state.json"
    payload_path.write_text(
        json.dumps(
            {
                "id": "harbor-docks",
                "name": "Greyhaven Docks",
                "tokens": [
                    {
                        "id": "captain-mira",
                        "name": "Captain Mira",
                        "x": 14,
                        "y": 7,
                        "hp_current": 22,
                        "hp_max": 35,
                        "initiative": 18,
                        "conditions": ["frightened 1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(200, json={"id": "harbor-docks", "name": "Greyhaven Docks"})

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
            "push_maptool_payload_file.py",
            "--file",
            str(payload_path),
            "--bridge-url",
            "http://127.0.0.1:5005",
        ],
    )

    assert main() == 0
    output = capsys.readouterr().out

    assert captured["url"] == "http://127.0.0.1:5005/bridge/map-state"
    assert '"id":"captain-mira"' in captured["payload"]
    assert '"name": "Greyhaven Docks"' in output


def test_push_maptool_payload_file_fails_on_invalid_payload(monkeypatch, tmp_path):
    payload_path = tmp_path / "invalid-map-state.json"
    payload_path.write_text(json.dumps({"name": "Missing ID"}), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        [
            "push_maptool_payload_file.py",
            "--file",
            str(payload_path),
        ],
    )

    try:
        main()
    except Exception as exc:
        assert exc.__class__.__name__ == "ValidationError"
    else:
        raise AssertionError("Expected payload validation to fail")
