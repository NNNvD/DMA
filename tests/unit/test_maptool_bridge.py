from fastapi.testclient import TestClient

from scripts.maptool_bridge import create_bridge_app


def test_bridge_pushes_and_fetches_map_state_without_auth():
    client = TestClient(create_bridge_app())

    payload = {
        "id": "harbor-docks",
        "name": "Greyhaven Docks",
        "tokens": [
            {
                "id": "captain-mira",
                "name": "Captain Mira",
                "x": 14,
                "y": 7,
                "notes": "Holding the line",
                "layer": "objects",
                "hp_current": 22,
                "hp_max": 35,
                "initiative": 18,
                "conditions": ["frightened 1"],
            }
        ],
        "fog_state": "partial",
        "light_state": "dim",
    }

    push = client.post("/bridge/map-state", json=payload)
    fetch = client.get("/maps/harbor-docks")
    health = client.get("/health")

    assert push.status_code == 200
    assert fetch.status_code == 200
    assert health.status_code == 200
    assert fetch.json()["tokens"][0]["name"] == "Captain Mira"
    assert health.json()["protected"] is False
    assert health.json()["map_count"] == 1


def test_bridge_login_and_protected_routes():
    client = TestClient(
        create_bridge_app(
            username="gm",
            password="secret",
            bearer_token="bridge-token",
        )
    )

    unauthorized = client.get("/maps/demo")
    login = client.post("/auth/login", json={"username": "gm", "password": "secret"})
    authorized_push = client.post(
        "/bridge/map-state",
        headers={"Authorization": "Bearer bridge-token"},
        json={"id": "demo", "name": "Demo", "tokens": []},
    )
    authorized_fetch = client.get(
        "/maps/demo",
        headers={"Authorization": "Bearer bridge-token"},
    )

    assert unauthorized.status_code == 401
    assert login.status_code == 200
    assert login.json()["token"] == "bridge-token"
    assert authorized_push.status_code == 200
    assert authorized_fetch.status_code == 200
    assert authorized_fetch.json()["name"] == "Demo"
