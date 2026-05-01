import httpx
import pytest

from scripts.push_maptool_fixture import main

REAL_HTTPX_CLIENT = httpx.Client


def test_push_maptool_fixture_posts_expected_payload(monkeypatch, capsys):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={"id": "harbor-docks", "name": "Greyhaven Docks", "tokens": []},
        )

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

    monkeypatch.setattr("scripts.push_maptool_fixture.httpx.Client", MockClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "push_maptool_fixture.py",
            "--bridge-url",
            "http://127.0.0.1:5005",
            "--token",
            "bridge-token",
        ],
    )

    assert main() == 0
    output = capsys.readouterr().out

    assert captured["url"] == "http://127.0.0.1:5005/bridge/map-state"
    assert captured["authorization"] == "Bearer bridge-token"
    assert '"id":"harbor-docks"' in captured["payload"]
    assert '"initiative":21' in captured["payload"]
    assert '"name": "Greyhaven Docks"' in output


def test_push_maptool_fixture_raises_for_http_errors(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "bad token"})

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

    monkeypatch.setattr("scripts.push_maptool_fixture.httpx.Client", MockClient)
    monkeypatch.setattr("sys.argv", ["push_maptool_fixture.py"])

    with pytest.raises(httpx.HTTPStatusError):
        main()
