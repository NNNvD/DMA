import asyncio
import json

from fastapi.testclient import TestClient

from backend.config.settings import settings
from backend.models.maptool import CampaignMapState, CampaignToken
from tests.support.app_factory import create_documents_test_app


def _create_entity(client: TestClient, **payload):
    response = client.post("/api/campaign/entities", json=payload)
    assert response.status_code == 200
    return response.json()


def test_live_session_state_api_saves_hydrates_and_resets():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        docks = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven Docks",
            details={"category": "harbor"},
        )
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Talia Stormborn",
            current_location_id=docks["id"],
            details={"hooks": ["Investigate Dock 7"]},
        )
        npc = _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            current_location_id=docks["id"],
            details={"goals": ["Stabilize the harbor"]},
        )
        _create_entity(
            client,
            entity_type="calendar",
            name="Coast Reckoning",
            details={"current_date": {"year": 4726, "month": "Dawnswell", "day": 20}},
        )

        session_update = client.post(
            "/api/campaign/import/session-update",
            json={
                "title": "Session 12 - Harbor Fire",
                "content": """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=20
Summary: Dock 7 burned during the smuggler attack.

## NPC: Captain Mira
Status: exhausted
Location: Greyhaven Docks

## Changelog
- Captain Mira owes Talia a favor.
""",
            },
        )
        assert session_update.status_code == 200

        prep = client.post(
            "/api/prep/session-brief",
            json={
                "title": "Session 13 Prep",
                "focus": "harbor recovery",
                "current_location_id": docks["id"],
            },
        )
        assert prep.status_code == 200

        save = client.put(
            "/api/live/session-state",
            json={
                "scene_title": "Audience at Dock 7",
                "focus": "triage and interrogation",
                "current_location_id": docks["id"],
                "active_pc_ids": [pc["id"]],
                "active_npc_ids": [npc["id"]],
                "notes": "Keep the pressure on the smuggler lead.",
                "frugal_mode": True,
                "combat_state": {
                    "roomId": "A1",
                    "roomTitle": "Test Skirmish",
                    "round": 2,
                    "activeIndex": 1,
                    "combatants": [
                        {"name": "Mitflit", "hpTrack": [5], "maxHp": 10},
                        {"name": "Giant Fly", "hpTrack": [8], "maxHp": 8},
                    ],
                },
            },
        )
        assert save.status_code == 200
        payload = save.json()

        assert payload["state"]["scene_title"] == "Audience at Dock 7"
        assert payload["state"]["frugal_mode"] is True
        assert payload["state"]["combat_state"]["roomId"] == "A1"
        assert payload["state"]["combat_state"]["round"] == 2
        assert payload["state"]["combat_state"]["combatants"][0]["name"] == "Mitflit"
        assert payload["current_location"]["name"] == "Greyhaven Docks"
        assert [item["name"] for item in payload["active_pcs"]] == ["Talia Stormborn"]
        assert [item["name"] for item in payload["active_npcs"]] == ["Captain Mira"]
        assert payload["current_date"]["day"] == 20
        assert payload["recent_sessions"][0]["title"] == "Session 12 - Harbor Fire"
        assert payload["latest_prep"]["title"] == "Session 13 Prep"

        restored = client.get("/api/live/session-state")
        assert restored.status_code == 200
        restored_payload = restored.json()
        assert restored_payload["state"]["focus"] == "triage and interrogation"
        assert restored_payload["state"]["combat_state"]["activeIndex"] == 1
        assert (
            restored_payload["available"]["locations"][0]["name"] == "Greyhaven Docks"
        )

        reset = client.delete("/api/live/session-state")
        assert reset.status_code == 200
        reset_payload = reset.json()
        assert reset_payload["state"]["scene_title"] is None
        assert reset_payload["state"]["active_pc_ids"] == []
        assert reset_payload["state"]["frugal_mode"] is False
        assert reset_payload["state"]["combat_state"]["combatants"] == []
    finally:
        asyncio.run(engine.dispose())


def test_live_dungeon_map_and_room_key_routes(monkeypatch, tmp_path):
    map_root = tmp_path / "media"
    map_folder = map_root / "abomination-vaults" / "maps" / "BOOK 1"
    map_folder.mkdir(parents=True)
    map_file = map_folder / "Level1.jpg"
    map_file.write_bytes(b"fake image bytes")

    room_key_root = tmp_path / "room-keys"
    room_key_folder = room_key_root / "abomination-vaults"
    room_key_folder.mkdir(parents=True)
    vault_root = tmp_path / "vault"
    references_folder = vault_root / "Library" / "References"
    references_folder.mkdir(parents=True)
    (references_folder / "Abomination Vaults 1 Ruins Of Gauntlight.md").write_text(
        """
A1. DAMP ENTRANCE LOW 1
Wet      Right column note.
stone and original
boxed text near [[Campaign/Locations/Gauntlight Keep|Gauntlight Keep]].

Once the primary entrance
text stays included.

Creatures: Three mitflits
wait above the webs.

MITFLITS (3) CREATURE -1
Pathfinder Bestiary 192
Initiative Stealth +5

A2. DECREPIT DRAWBRIDGE
Rotten planks cross the water. The chains look ready to fall apart,
giving the drawbridge's structural integrity an extra layer of dubiousness.
True to appearances, the drawbridge isn't safe to cross.

A25. GAUNTLIGHT CUPOLA MODERATE 1
Rows of black metal bars encase this circular chamber
like a cage.

CHAPTER 2:
The Forgotten Dungeon
This text belongs to the next chapter, not A25.
""".strip(),
        encoding="utf-8",
    )
    (room_key_folder / "level-1.json").write_text(
        json.dumps(
            {
                "map_id": "level1",
                "title": "Level 1",
                "rooms": [
                    {
                        "room_id": "A1",
                        "title": "Damp Entrance",
                        "player_visible_description": "Wet stone and webs.",
                        "source": "Abomination Vaults 1 - Ruins of Gauntlight.pdf, p. 6",
                    },
                    {
                        "room_id": "A25",
                        "title": "Gauntlight Cupola",
                        "player_visible_description": "The cupola.",
                        "source": "Abomination Vaults 1 - Ruins of Gauntlight.pdf, p. 17",
                    },
                    {
                        "room_id": "A2",
                        "title": "Decrepit Drawbridge",
                        "player_visible_description": "The drawbridge.",
                        "source": "Abomination Vaults 1 - Ruins of Gauntlight.pdf, p. 6",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    bestiary_folder = tmp_path / "bestiary" / "abomination-vaults"
    bestiary_folder.mkdir(parents=True)
    (bestiary_folder / "level-3.json").write_text(
        json.dumps(
            {
                "campaign": "Abomination Vaults",
                "level": "Level 3 / C Rooms",
                "entries": [
                    {
                        "id": "av-l3-canker-cultist",
                        "entry_type": "creature",
                        "name": "Canker Cultist",
                        "level": 3,
                        "rooms": ["C15"],
                        "traits": ["Ghoul", "Undead"],
                        "summary": "Custom ghoul cultist.",
                        "combat": {"ac": "19", "hp": "45"},
                    },
                    {
                        "id": "av-l3-watching-wall",
                        "entry_type": "hazard",
                        "name": "Watching Wall",
                        "level": 4,
                        "rooms": ["C4"],
                        "summary": "Complex haunt.",
                    },
                    {
                        "id": "av-l3-ghoul-fever",
                        "entry_type": "affliction",
                        "name": "Ghoul Fever",
                        "rooms": ["C15"],
                        "affliction": {"dc": "20"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "dungeon_map_root", str(map_root))
    monkeypatch.setattr(settings, "dungeon_room_key_root", str(room_key_root))
    monkeypatch.setattr(settings, "obsidian_vault_path", str(vault_root))

    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        maps = client.get("/api/live/dungeon-maps")
        assert maps.status_code == 200
        map_payload = maps.json()
        assert map_payload["total"] == 1
        assert map_payload["items"][0]["map_id"] == "level1"
        assert map_payload["items"][0]["path"].endswith("Level1.jpg")

        image = client.get(
            "/api/live/dungeon-map",
            params={"path": "abomination-vaults/maps/BOOK 1/Level1.jpg"},
        )
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/jpeg"
        assert image.content == b"fake image bytes"

        unsafe = client.get("/api/live/dungeon-map", params={"path": "../Level1.jpg"})
        assert unsafe.status_code == 400

        room_key = client.get("/api/live/dungeon-room-key", params={"map_id": "level1"})
        assert room_key.status_code == 200
        room_payload = room_key.json()
        assert room_payload["title"] == "Level 1"
        assert room_payload["rooms"][0]["room_id"] == "A1"
        assert (
            room_payload["rooms"][0]["literal_text"]["read_aloud"]
            == "Wet stone and original boxed text near Gauntlight Keep."
        )
        assert (
            room_payload["rooms"][0]["literal_text"]["general_text"]
            == "Once the primary entrance text stays included.\n\nCreatures: Three mitflits wait above the webs."
        )
        assert (
            room_payload["rooms"][0]["literal_text"]["encounter_text"]
            == "MITFLITS (3) CREATURE -1 Pathfinder Bestiary 192\nInitiative Stealth +5"
        )
        a25 = room_payload["rooms"][1]["literal_text"]
        assert a25["read_aloud"] == (
            "Rows of black metal bars encase this circular chamber like a cage."
        )
        assert "The Forgotten Dungeon" not in json.dumps(a25)
        assert "next chapter" not in json.dumps(a25)
        a2 = room_payload["rooms"][2]["literal_text"]
        assert a2["read_aloud"].endswith("dubiousness.")
        assert a2["general_text"] == (
            "True to appearances, the drawbridge isn't safe to cross."
        )

        bestiary = client.get("/api/live/campaign-bestiary")
        assert bestiary.status_code == 200
        assert {item["id"] for item in bestiary.json()["items"]} == {
            "av-l3-canker-cultist",
            "av-l3-watching-wall",
            "av-l3-ghoul-fever",
        }

        filtered = client.get(
            "/api/live/campaign-bestiary",
            params={"entry_type": "creature", "q": "canker"},
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()["items"]] == [
            "av-l3-canker-cultist"
        ]

        detail = client.get(
            "/api/live/campaign-bestiary-entry",
            params={"id": "av-l3-ghoul-fever"},
        )
        assert detail.status_code == 200
        assert detail.json()["entry"]["affliction"]["dc"] == "20"

        missing = client.get(
            "/api/live/campaign-bestiary-entry",
            params={"id": "missing"},
        )
        assert missing.status_code == 404
    finally:
        asyncio.run(engine.dispose())


def test_live_pc_sheet_and_npc_dossier_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.api.routes.live.settings.obsidian_vault_path",
        str(tmp_path / "missing-vault"),
    )
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        pc_sheet = client.post(
            "/api/campaign/import/pc-sheet",
            json={
                "title": "Talia Sheet",
                "source_name": "pathbuilder/test/Talia.json",
                "content": """
Name: Talia Stormborn
Class: Ranger
Level: 4
Ancestry: Human
Background: Scout
Languages: Common, Elven
Attributes: str=14, dex=18, con=12, int=10, wis=16, cha=8
Skills: Acrobatics, Stealth, Survival
Items: Longbow, Leather Armor
""",
            },
        )
        assert pc_sheet.status_code == 200
        pc_id = pc_sheet.json()["pc"]["id"]

        npc = _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            summary="Harbor watch commander.",
            description="A stern but fair commander who keeps the docks stable.",
            details={
                "role": "watch commander",
                "status": "exhausted",
                "status_detail": "Has not slept since the harbor fire.",
                "appearance_description": "A rain-soaked commander in a battered blue coat.",
                "gm_summary": "Mira is overworked but reliable.",
                "pc_encountered": True,
                "pc_relationship_status": "friendly",
                "campaign_encounters": ["Harbor fire aftermath"],
                "goals": ["Stabilize the harbor"],
                "secrets": ["Knows a smuggler route"],
                "portrait": "/assets/mira.png",
            },
        )

        pcs = client.get("/api/live/pc-sheets")
        assert pcs.status_code == 200
        pc_items = pcs.json()["items"]
        assert pc_items[0]["character_name"] == "Talia Stormborn"
        assert pc_items[0]["player_name"] == "Talia"
        assert "combat" in pc_items[0]
        assert "skills" in pc_items[0]
        assert pc_items[0]["identity"]["class_name"] == "Ranger"

        pc_view = client.get("/api/live/pc-sheet", params={"id": pc_id})
        assert pc_view.status_code == 200
        pc_payload = pc_view.json()
        assert pc_payload["character_name"] == "Talia Stormborn"
        assert pc_payload["identity"]["class_name"] == "Ranger"
        assert pc_payload["identity"]["level"] == 4
        assert pc_payload["has_imported_sheet"] is True

        npcs = client.get("/api/live/npc-sheets", params={"q": "mira"})
        assert npcs.status_code == 200
        npc_item = npcs.json()["items"][0]
        assert npc_item["name"] == "Captain Mira"
        assert npc_item["status_detail"] == "Has not slept since the harbor fire."
        assert npc_item["pc_encountered"] is True
        assert npc_item["pc_relationship_status"] == "friendly"
        assert npc_item["campaign_encounters"] == ["Harbor fire aftermath"]

        npc_view = client.get("/api/live/npc-sheet", params={"id": npc["id"]})
        assert npc_view.status_code == 200
        npc_payload = npc_view.json()
        assert npc_payload["name"] == "Captain Mira"
        assert npc_payload["role"] == "watch commander"
        assert npc_payload["portrait"] == "/assets/mira.png"
        assert npc_payload["image"]["url"] == "/assets/mira.png"
        assert npc_payload["image"]["status"] == "local"
        assert npc_payload["goals"] == ["Stabilize the harbor"]
        assert npc_payload["appearance_description"].startswith("A rain-soaked")
        assert npc_payload["gm_summary"] == "Mira is overworked but reliable."
        assert npc_payload["pc_encountered"] is True
        assert npc_payload["pc_relationship_status"] == "friendly"
        assert npc_payload["campaign_encounters"] == ["Harbor fire aftermath"]

        npc_update = client.patch(
            "/api/live/npc-sheet",
            params={"id": npc["id"]},
            json={
                "pc_relationship_status": "ally",
                "status": "active",
                "status_detail": "Ready to brief the party.",
                "campaign_encounters": ["Harbor fire aftermath", "Session 13"],
                "vault_dm_notes": "Mira trusts Talia with sensitive leads.",
                "vault_player_summary": "A stern harbor commander who helped after the fire.",
            },
        )
        assert npc_update.status_code == 200
        updated_payload = npc_update.json()
        assert updated_payload["pc_relationship_status"] == "ally"
        assert updated_payload["status"] == "active"
        assert updated_payload["status_detail"] == "Ready to brief the party."
        assert updated_payload["dm_notes"] == "Mira trusts Talia with sensitive leads."
        assert updated_payload["player_facing"].startswith("A stern harbor commander")
        assert updated_payload["campaign_encounters"] == [
            "Harbor fire aftermath",
            "Session 13",
        ]
    finally:
        asyncio.run(engine.dispose())


def test_live_vault_image_wikilinks_become_browser_urls(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    sheet_dir = vault_root / "Sheets"
    asset_dir = vault_root / "Library" / "Assets" / "Portraits" / "PCs"
    sheet_dir.mkdir(parents=True)
    asset_dir.mkdir(parents=True)
    (asset_dir / "Daan.png").write_bytes(b"fake portrait")
    (sheet_dir / "Daan.md").write_text(
        """
---
document_kind: "pc_sheet"
title: "Daan"
pc_name: "Bonesy McBoner"
imageLink: "[[Library/Assets/Portraits/PCs/Daan.png]]"
image_status: "confirmed"
image_source: "player supplied"
---
# Daan
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.api.routes.live.settings.obsidian_vault_path",
        str(vault_root),
    )
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        sheets = client.get("/api/live/pc-sheets")
        assert sheets.status_code == 200
        payload = sheets.json()["items"][0]
        assert payload["portrait"].startswith("/api/live/vault/file?path=")
        assert payload["image"]["status"] == "confirmed"
        assert payload["image"]["source"] == "player supplied"
        image = client.get(payload["portrait"])
        assert image.status_code == 200
        assert image.content == b"fake portrait"
    finally:
        asyncio.run(engine.dispose())


def test_live_vault_pc_sheet_can_reuse_linked_local_json(tmp_path, monkeypatch):
    vault_root = tmp_path / "vault"
    sheet_dir = vault_root / "Sheets"
    source_dir = tmp_path / "assets" / "imports" / "pathbuilder" / "test"
    sheet_dir.mkdir(parents=True)
    source_dir.mkdir(parents=True)
    source_path = source_dir / "Max.json"
    source_path.write_text(
        json.dumps(
            {
                "success": True,
                "build": {
                    "name": "Shmungus",
                    "class": "Druid",
                    "level": 1,
                    "ancestry": "Leshy",
                    "heritage": "Fungus Leshy",
                    "background": "Plant Whisperer",
                    "abilities": {"str": 14, "dex": 14, "con": 14, "int": 8, "wis": 18, "cha": 10},
                    "attributes": {"ancestryhp": 8, "classhp": 8, "speed": 25},
                    "proficiencies": {"classDC": 2, "perception": 2, "fortitude": 2, "reflex": 2, "will": 4},
                    "acTotal": {"acTotal": 16},
                    "weapons": [{"name": "Thundermace"}],
                },
            }
        ),
        encoding="utf-8",
    )
    (sheet_dir / "Max.md").write_text(
        f"""
---
document_kind: "pc_sheet"
title: "Max"
pc_name: "Shmungus"
source_url: "{source_path}"
---
# Max
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.api.routes.live.settings.obsidian_vault_path",
        str(vault_root),
    )
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        sheets = client.get("/api/live/pc-sheets")
        assert sheets.status_code == 200
        payload = sheets.json()["items"][0]
        assert payload["character_name"] == "Shmungus"
        assert payload["identity"]["class_name"] == "Druid"
        assert payload["combat"]["ac"] == 16
        full_sheet = client.get("/api/live/pc-sheet", params={"id": payload["id"]}).json()
        assert full_sheet["attacks"][0]["name"] == "Thundermace"
    finally:
        asyncio.run(engine.dispose())


def test_live_pc_sheet_routes_load_obsidian_vault_sheets(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    sheets = vault / "Sheets"
    sheets.mkdir(parents=True)
    (sheets / "Yorick.md").write_text(
        """---
document_kind: "pc_sheet"
doc_id: 42
title: "Yorick"
summary: "Imported Pathbuilder 2 sheet for Fahral at level 1."
source_name: "pathbuilder/abomination-vaults/Yorick.json"
pc_name: "Fahral"
class_name: "Rogue"
level: 1
ancestry: "Elf"
heritage: "Whisper Elf"
background: "Fire Warden"
alignment: "N"
key_ability: "dex"
speed: 30
armor_class: 17
perception: 4
initiative: 4
fortitude: 2
reflex: 4
will: 4
stealth: 2
thievery: 2
special_abilities: ["Sneak Attack", "Low-Light Vision"]
---
# Yorick

```json
{"build":{"name":"Fahral","class":"Rogue","level":1,"ancestry":"Elf","heritage":"Whisper Elf","background":"Fire Warden","alignment":"N","keyability":"dex","abilities":{"str":14,"dex":18,"con":8,"int":12,"wis":12,"cha":14},"attributes":{"ancestryhp":6,"classhp":8,"bonushp":0,"bonushpPerLevel":0,"speed":30},"proficiencies":{"classDC":2,"perception":4,"fortitude":2,"reflex":4,"will":4,"stealth":2,"thievery":2},"acTotal":{"acTotal":17},"specials":["Sneak Attack","Low-Light Vision"],"weapons":[]}}
```
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.api.routes.live.settings.obsidian_vault_path",
        str(vault),
    )

    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.get("/api/live/pc-sheets")
        assert response.status_code == 200
        payload = response.json()
        assert payload["source"] == "obsidian_vault"
        assert payload["items"][0]["id"] == 42
        assert payload["items"][0]["player_name"] == "Yorick"
        assert payload["items"][0]["character_name"] == "Fahral"
        assert payload["items"][0]["identity"]["class_name"] == "Rogue"

        detail = client.get("/api/live/pc-sheet", params={"id": 42})
        assert detail.status_code == 200
        assert detail.json()["combat"]["ac"] == 17
        assert detail.json()["combat"]["speed"] == 30
        assert detail.json()["specials"] == ["Sneak Attack", "Low-Light Vision"]
    finally:
        asyncio.run(engine.dispose())


def test_live_command_center_overview_routes_create_and_update_vault_notes(
    tmp_path,
    monkeypatch,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(
        "backend.api.routes.live.settings.obsidian_vault_path",
        str(vault),
    )

    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        campaign = client.get("/api/live/campaign-overview")
        assert campaign.status_code == 200
        campaign_payload = campaign.json()
        assert campaign_payload["path"] == "Command Center/Campaign Overview.md"
        assert "## Campaign Premise" in campaign_payload["content"]

        updated_campaign = client.patch(
            "/api/live/campaign-overview",
            json={"content": "# Campaign Overview\n\n## DM Notes\n\nUpdated notes."},
        )
        assert updated_campaign.status_code == 200
        assert "Updated notes." in updated_campaign.json()["content"]

        sessions = client.get("/api/live/session-overviews")
        assert sessions.status_code == 200
        session_items = sessions.json()["items"]
        assert any(item["title"] == "Next Session" for item in session_items)

        next_session_path = next(
            item["path"] for item in session_items if item["title"] == "Next Session"
        )
        session = client.get(
            "/api/live/session-overview",
            params={"path": next_session_path},
        )
        assert session.status_code == 200
        assert "## Session Goal" in session.json()["content"]

        updated_session = client.patch(
            "/api/live/session-overview",
            params={"path": next_session_path},
            json={"content": "# Next Session\n\n## Session Notes\n\nTest note."},
        )
        assert updated_session.status_code == 200
        assert "Test note." in updated_session.json()["content"]
    finally:
        asyncio.run(engine.dispose())


def test_live_assistant_route_handles_scene_rules_continuity_recap_and_prep():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        docks = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven Docks",
            summary="The busiest harbor district in the city.",
            details={"category": "harbor"},
        )
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Talia Stormborn",
            current_location_id=docks["id"],
            details={"hooks": ["Investigate Dock 7"]},
        )
        npc = _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            summary="Harbor watch commander trying to hold the line.",
            current_location_id=docks["id"],
            details={"goals": ["Stabilize the harbor"], "status": "exhausted"},
        )
        _create_entity(
            client,
            entity_type="calendar",
            name="Coast Reckoning",
            details={"current_date": {"year": 4726, "month": "Dawnswell", "day": 20}},
        )

        rule_doc = client.post(
            "/api/documents",
            json={
                "title": "Frightened",
                "kind": "rule",
                "source_name": "AoN Test",
                "source_class": "retrieval_only",
                "privacy_scope": "public",
                "review_status": "approved",
                "visibility_scope": "player_safe",
                "rag_eligible": True,
                "train_eligible": False,
                "content": (
                    "Frightened always includes a value. You take a status penalty "
                    "equal to this value to all checks and DCs. At the end of each of "
                    "your turns, the value decreases by 1."
                ),
            },
        )
        assert rule_doc.status_code == 200

        session_update = client.post(
            "/api/campaign/import/session-update",
            json={
                "title": "Session 12 - Harbor Fire",
                "content": """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=20
Summary: Dock 7 burned during the smuggler attack.

## NPC: Captain Mira
Status: exhausted
Location: Greyhaven Docks

## Changelog
- Captain Mira owes Talia a favor.
""",
            },
        )
        assert session_update.status_code == 200

        save = client.put(
            "/api/live/session-state",
            json={
                "scene_title": "Audience at Dock 7",
                "focus": "triage and interrogation",
                "current_location_id": docks["id"],
                "active_pc_ids": [pc["id"]],
                "active_npc_ids": [npc["id"]],
                "notes": "Keep the pressure on the smuggler lead.",
                "frugal_mode": True,
            },
        )
        assert save.status_code == 200

        scene = client.post("/api/live/respond", json={"message": "/scene"})
        assert scene.status_code == 200
        scene_payload = scene.json()
        assert scene_payload["mode"] == "scene"
        assert "Audience at Dock 7" in scene_payload["answer"]
        assert "Captain Mira" in scene_payload["answer"]

        rules = client.post(
            "/api/live/respond",
            json={"message": "/rules frightened"},
        )
        assert rules.status_code == 200
        rules_payload = rules.json()
        assert rules_payload["mode"] == "rules"
        assert "frightened" in rules_payload["answer"].lower()
        assert rules_payload["citations"]

        continuity = client.post(
            "/api/live/respond",
            json={"message": "Captain Mira"},
        )
        assert continuity.status_code == 200
        continuity_payload = continuity.json()
        assert continuity_payload["mode"] == "continuity"
        assert "Best match: Captain Mira" in continuity_payload["answer"]
        assert "Stabilize the harbor" in continuity_payload["answer"]
        assert continuity_payload["entities"][0]["name"] == "Captain Mira"

        recap = client.post("/api/live/respond", json={"message": "/recap"})
        assert recap.status_code == 200
        recap_payload = recap.json()
        assert recap_payload["mode"] == "recap"
        assert "Session 12 - Harbor Fire" in recap_payload["answer"]

        prep = client.post("/api/live/respond", json={"message": "/prep"})
        assert prep.status_code == 200
        prep_payload = prep.json()
        assert prep_payload["mode"] == "prep"
        assert "Live Session Brief" in prep_payload["answer"]
        assert prep_payload["prep"]["markdown"].startswith("# Live Session Brief")

        improv_npc = client.post(
            "/api/live/respond",
            json={"message": "/npc suspicious dock clerk"},
        )
        assert improv_npc.status_code == 200
        improv_payload = improv_npc.json()
        assert improv_payload["mode"] == "npc"
        assert "Improvised NPC" in improv_payload["answer"]
        assert improv_payload["npc"]["role"] == "suspicious dock clerk"
    finally:
        asyncio.run(engine.dispose())


def test_live_maptool_sync_persists_mechanics_snapshot(monkeypatch):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    async def fake_pull_map_state(map_id: str, auth_header=None, retries=None):
        assert map_id == "dock-encounter"
        assert auth_header == "Bearer session-token"
        assert retries == 2
        return CampaignMapState(
            map_id="dock-encounter",
            name="Dock Encounter",
            tokens=[
                CampaignToken(
                    token_id="captain-mira",
                    label="Captain Mira",
                    x=1,
                    y=2,
                    hp_current=18,
                    hp_max=30,
                    initiative=21,
                    conditions=["frightened 1"],
                ),
                CampaignToken(
                    token_id="smuggler",
                    label="Smuggler",
                    x=4,
                    y=5,
                    hp_current=6,
                    hp_max=24,
                    initiative=15,
                    conditions=[],
                ),
            ],
            fog_state="clear",
            light_state="dim",
        )

    monkeypatch.setattr(
        "backend.services.live_maptool_service.maptool_adapter.pull_map_state",
        fake_pull_map_state,
    )

    try:
        save = client.put(
            "/api/live/session-state",
            json={
                "scene_title": "Dock Standoff",
                "focus": "combat escalation",
                "maptool_map_id": "dock-encounter",
            },
        )
        assert save.status_code == 200

        sync = client.post(
            "/api/live/maptool-sync",
            json={"retries": 2},
            headers={"Authorization": "Bearer session-token"},
        )
        assert sync.status_code == 200
        payload = sync.json()

        assert payload["state"]["maptool_map_id"] == "dock-encounter"
        assert payload["maptool"]["name"] == "Dock Encounter"
        assert payload["maptool"]["mechanics"]["summary"]["initiative_count"] == 2
        assert payload["maptool"]["mechanics"]["summary"]["low_hp_count"] == 1
        assert (
            payload["maptool"]["mechanics"]["initiative_order"][0]["label"]
            == "Captain Mira"
        )
        assert (
            payload["maptool"]["mechanics"]["conditioned_tokens"][0]["label"]
            == "Captain Mira"
        )

        restored = client.get("/api/live/session-state")
        assert restored.status_code == 200
        restored_payload = restored.json()
        assert restored_payload["maptool"]["map_id"] == "dock-encounter"
    finally:
        asyncio.run(engine.dispose())


def test_dm_panel_route_serves_browser_panel():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.get("/dm-panel")
        assert response.status_code == 200
        assert "DMA DM Panel" in response.text
        assert "/api/live/session-state" in response.text
        assert "/api/live/maptool-sync" in response.text
        assert "/api/live/respond" in response.text
        assert "/api/live/vault/notes" in response.text
        assert "/api/live/reference-pdfs" in response.text
        assert "Live Assistant" not in response.text
        assert "DMA Chat Workbench" in response.text
        assert "Session Context" in response.text
        assert "Vault Workspace" in response.text
        assert "Export DMA To Vault" in response.text
        assert "Sync Vault To DMA" in response.text
        assert "Reference PDFs" in response.text
        assert "How to use this module" in response.text
        assert "Dice Roller" in response.text
        assert "Session Soundboard" in response.text
        assert "Voice Reader" in response.text
        assert "/api/live/tts/status" in response.text
        assert "/api/live/tts/synthesize" in response.text
        assert "Piper Local Narrator" in response.text
        assert "1d20+7" in response.text
        assert "speechSynthesis" in response.text
        assert "Session Mechanics" in response.text
        assert "Campaign Overview" in response.text
        assert "Treasure Tracker" in response.text
        assert 'data-campaign-tab="items"' in response.text
        assert "Session Overview" in response.text
        assert "Quick Rules" in response.text
        assert "/scene" in response.text
        assert "/rules" in response.text
        assert "/recap" in response.text
        assert "/prep" in response.text
        assert "/search" in response.text
        assert "Continuity Search" in response.text
    finally:
        asyncio.run(engine.dispose())


def test_live_tts_status_defaults_to_browser():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.get("/api/live/tts/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "browser"
        assert payload["browser_available"] is True
        assert payload["piper_ready"] is False
    finally:
        asyncio.run(engine.dispose())


def test_live_tts_synthesize_requires_piper(monkeypatch):
    monkeypatch.setattr("backend.api.routes.live.settings.tts_provider", "browser")

    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.post("/api/live/tts/synthesize", json={"text": "Hello"})
        assert response.status_code == 400
        assert "Server TTS is not enabled" in response.json()["detail"]
    finally:
        asyncio.run(engine.dispose())


def test_live_tts_status_reports_unconfigured_piper(monkeypatch):
    monkeypatch.setattr("backend.api.routes.live.settings.tts_provider", "piper")
    monkeypatch.setattr("backend.api.routes.live.settings.piper_voice_path", None)

    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        response = client.get("/api/live/tts/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "piper"
        assert payload["piper_ready"] is False
        assert "PIPER_VOICE_PATH" in payload["piper_detail"]
    finally:
        asyncio.run(engine.dispose())


def test_live_panel_vault_and_pdf_helpers_are_scoped(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Command Center").mkdir()
    (vault / "Command Center" / "Start Here.md").write_text(
        "# Start Here\n\nUse this campaign dashboard.",
        encoding="utf-8",
    )
    (vault / "ignore.txt").write_text("not a note", encoding="utf-8")

    pdf_root = tmp_path / "pdfs"
    pdf_root.mkdir()
    (pdf_root / "book.pdf").write_bytes(b"%PDF-1.4\n%dma-test\n")

    monkeypatch.setattr(
        "backend.api.routes.live.settings.obsidian_vault_path",
        str(vault),
    )
    monkeypatch.setattr(
        "backend.api.routes.live.settings.reference_pdf_root",
        str(pdf_root),
    )

    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        notes = client.get("/api/live/vault/notes")
        assert notes.status_code == 200
        note_items = notes.json()["items"]
        assert note_items[0]["path"] == "Command Center/Start Here.md"

        note = client.get(
            "/api/live/vault/note",
            params={"path": "Command Center/Start Here.md"},
        )
        assert note.status_code == 200
        assert "campaign dashboard" in note.json()["content"]

        resolved_title = client.get(
            "/api/live/vault/resolve-link",
            params={"target": "Start Here"},
        )
        assert resolved_title.status_code == 200
        assert resolved_title.json()["path"] == "Command Center/Start Here.md"

        resolved_path = client.get(
            "/api/live/vault/resolve-link",
            params={"target": "Command Center/Start Here#Opening"},
        )
        assert resolved_path.status_code == 200
        assert resolved_path.json()["path"] == "Command Center/Start Here.md"
        assert resolved_path.json()["heading"] == "Opening"

        missing_link = client.get(
            "/api/live/vault/resolve-link",
            params={"target": "Missing Note"},
        )
        assert missing_link.status_code == 404

        escape = client.get("/api/live/vault/note", params={"path": "../secret.md"})
        assert escape.status_code == 400

        pdfs = client.get("/api/live/reference-pdfs")
        assert pdfs.status_code == 200
        assert pdfs.json()["items"][0]["path"] == "book.pdf"

        pdf = client.get("/api/live/reference-pdf", params={"path": "book.pdf"})
        assert pdf.status_code == 200
        assert pdf.headers["content-type"].startswith("application/pdf")
    finally:
        asyncio.run(engine.dispose())
