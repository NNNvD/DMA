import asyncio
import re

from fastapi.testclient import TestClient

from tests.support.app_factory import create_documents_test_app


def _create_entity(client: TestClient, **payload):
    response = client.post("/api/campaign/entities", json=payload)
    assert response.status_code == 200
    return response.json()


def test_campaign_queries_cover_location_language_and_relationship_filters():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        city = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven",
            details={
                "category": "city",
                "region": "The Sapphire Coast",
                "languages": ["Common", "Dwarvish"],
            },
        )
        faction = _create_entity(
            client,
            entity_type="faction",
            name="Lantern Guild",
            details={
                "agenda": "Protect trade routes",
                "languages": ["Common"],
            },
        )
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Talia Stormborn",
            current_location_id=city["id"],
            details={
                "role": "ranger",
                "languages": ["Common"],
                "hooks": ["Find the vanished warden"],
            },
        )
        _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            current_location_id=city["id"],
            details={
                "role": "harbor master",
                "languages": ["Common", "Varisian"],
            },
        )

        response = client.post(
            "/api/campaign/relationships",
            json={
                "source_entity_id": pc["id"],
                "target_entity_id": faction["id"],
                "relationship_type": "member",
                "notes": "Talia scouts for the guild when ships go missing.",
            },
        )
        assert response.status_code == 200

        response = client.post(
            f"/api/campaign/entities/{pc['id']}/sheet-versions",
            json={
                "source_name": "Level 3 update",
                "sheet": {
                    "class_name": "Ranger",
                    "level": 3,
                    "languages": ["Common", "Elven"],
                    "items": ["Moonbow", {"name": "Wayfinder Compass"}],
                    "goals": ["Find the vanished warden"],
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["version_number"] == 1

        location_query = client.get(
            "/api/campaign/entities",
            params={"entity_type": "npc", "current_location_id": city["id"]},
        )
        assert location_query.status_code == 200
        payload = location_query.json()
        assert payload["total"] == 1
        assert payload["items"][0]["name"] == "Captain Mira"

        language_query = client.get(
            "/api/campaign/entities", params={"language": "Elven"}
        )
        assert language_query.status_code == 200
        language_payload = language_query.json()
        assert {item["name"] for item in language_payload["items"]} == {
            "Talia Stormborn"
        }

        faction_ties_query = client.get(
            "/api/campaign/entities",
            params={"relationship_type": "member", "related_entity_id": pc["id"]},
        )
        assert faction_ties_query.status_code == 200
        ties_payload = faction_ties_query.json()
        assert ties_payload["total"] == 1
        assert ties_payload["items"][0]["name"] == "Lantern Guild"

        relationships = client.get(f"/api/campaign/entities/{pc['id']}/relationships")
        assert relationships.status_code == 200
        relationship_payload = relationships.json()
        assert relationship_payload["relationships"][0]["related_entity"]["name"] == (
            "Lantern Guild"
        )
    finally:
        asyncio.run(engine.dispose())


def test_campaign_overview_includes_artifacts_calendar_and_shop_state():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        city = _create_entity(
            client,
            entity_type="location",
            name="Saltmarket",
            details={"category": "port town"},
        )
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Iria Vale",
            current_location_id=city["id"],
            details={"role": "bard"},
        )
        _create_entity(
            client,
            entity_type="artifact",
            name="Moonwake Lute",
            owner_entity_id=pc["id"],
            current_location_id=city["id"],
            details={"rarity": "rare", "artifact_type": "instrument"},
        )
        _create_entity(
            client,
            entity_type="shop",
            name="Brass Lantern Outfitters",
            current_location_id=city["id"],
            details={
                "category": "outfitter",
                "owner_name": "Sella Vane",
                "stock_summary": ["Rope", "Lantern oil", "Climbing kits"],
            },
        )
        _create_entity(
            client,
            entity_type="calendar",
            name="Coast Reckoning",
            details={
                "months": ["Dawnswell", "Tidewane"],
                "weekdays": ["Moonday", "Stormday"],
                "current_date": {"year": 4726, "month": "Dawnswell", "day": 18},
            },
        )
        _create_entity(
            client,
            entity_type="holiday",
            name="Night of Tides",
            current_location_id=city["id"],
            details={"date_label": "Dawnswell 21", "recurrence": "annual"},
        )

        response = client.get("/api/campaign/overview")
        assert response.status_code == 200
        payload = response.json()

        assert payload["counts"]["artifact"] == 1
        assert payload["counts"]["calendar"] == 1
        assert payload["counts"]["holiday"] == 1
        assert payload["artifacts"][0]["owner_entity"]["name"] == "Iria Vale"
        assert payload["shops"][0]["current_location"]["name"] == "Saltmarket"
        assert payload["calendars"][0]["details"]["current_date"]["day"] == 18
    finally:
        asyncio.run(engine.dispose())


def test_pc_sheet_versions_increment_and_update_latest_sheet_state():
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        pc = _create_entity(
            client,
            entity_type="pc",
            name="Neris Vale",
            details={"role": "wizard"},
        )

        first = client.post(
            f"/api/campaign/entities/{pc['id']}/sheet-versions",
            json={
                "source_name": "Level 1 sheet",
                "sheet": {
                    "class_name": "Wizard",
                    "level": 1,
                    "languages": ["Common", "Draconic"],
                    "items": ["Spellbook"],
                },
            },
        )
        assert first.status_code == 200
        assert first.json()["version_number"] == 1

        second = client.post(
            f"/api/campaign/entities/{pc['id']}/sheet-versions",
            json={
                "source_name": "Level 2 sheet",
                "sheet": {
                    "class_name": "Wizard",
                    "level": 2,
                    "languages": ["Common", "Draconic", "Elven"],
                    "items": ["Spellbook", {"name": "Pearl of Power"}],
                },
            },
        )
        assert second.status_code == 200
        assert second.json()["version_number"] == 2

        versions = client.get(f"/api/campaign/entities/{pc['id']}/sheet-versions")
        assert versions.status_code == 200
        payload = versions.json()
        assert [version["version_number"] for version in payload["versions"]] == [1, 2]

        entity = client.get(f"/api/campaign/entities/{pc['id']}")
        assert entity.status_code == 200
        entity_payload = entity.json()
        assert entity_payload["latest_sheet_version"]["version_number"] == 2
        assert entity_payload["details"]["level"] == 2
        assert entity_payload["details"]["languages"] == [
            "Common",
            "Draconic",
            "Elven",
        ]
        assert "Pearl of Power" in entity_payload["details"]["notable_items"]
    finally:
        asyncio.run(engine.dispose())


def test_obsidian_vault_export_writes_campaign_notes_indexes_and_documents(tmp_path):
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
            details={"hooks": ["Investigate the ledger"], "languages": ["Common"]},
        )
        _create_entity(client, entity_type="faction", name="Lantern Guild")
        npc = _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            current_location_id=docks["id"],
            details={"role": "harbor master", "languages": ["Common", "Varisian"]},
            tags=["harbor"],
        )

        relationship = client.post(
            "/api/campaign/relationships",
            json={
                "source_entity_id": npc["id"],
                "target_entity_id": pc["id"],
                "relationship_type": "ally",
                "notes": "Keeps a weather eye on the ranger.",
            },
        )
        assert relationship.status_code == 200

        pc_sheet = client.post(
            "/api/campaign/import/pc-sheet",
            json={
                "title": "Talia Sheet",
                "content": """---
tags:
  - player
  - main-party
---
Name: Talia Stormborn
Class: Ranger
Level: 4
Languages: Common, Elven
Location: [[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]
Factions: [[Campaign/Factions/Lantern Guild|Lantern Guild]]
Relationships: contact -> [[Campaign/NPCs/Captain Mira|Captain Mira]]
Items: Moonbow, Healing Potion
Notable Items: Moonbow, Wayfinder Compass
""",
            },
        )
        assert pc_sheet.status_code == 200

        campaign_note = client.post(
            "/api/campaign/import/notes",
            json={
                "title": "Port Rumors",
                "content": """
## Location: Greyhaven Docks
Summary: The docks remain tense after the fire in Greyhaven Docks.

## NPC: Captain Mira
Hooks:
- Needs help stabilizing trade.
""",
            },
        )
        assert campaign_note.status_code == 200

        reference_doc = client.post(
            "/api/documents",
            json={
                "title": "Absalom Harbor Guide",
                "kind": "reference",
                "content": (
                    "Greyhaven Docks handles most inbound trade. "
                    "Captain Mira tracks harbor permits."
                ),
                "summary": "Imported PDF reference excerpt.",
                "source_name": "misc/private-local/reference/raw/player/harbor-guide.pdf",
                "url": "/tmp/harbor-guide.pdf",
                "visibility_scope": "player_safe",
                "rag_eligible": True,
                "train_eligible": False,
            },
        )
        assert reference_doc.status_code == 200

        session_update = client.post(
            "/api/campaign/import/session-update",
            json={
                "title": "Session 12 - Harbor Fire",
                "content": """
Calendar: Coast Reckoning
Current Date: year=4726; month=Dawnswell; day=20
Summary: Dock 7 burned during the smuggler attack.
Timeline Position: session-12

## NPC: Captain Mira
Status: exhausted
Location: [[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]

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
                "current_location_id": docks["id"],
                "focus": "harbor recovery",
            },
        )
        assert prep.status_code == 200

        vault_path = tmp_path / "vault"
        response = client.post(
            "/api/campaign/export/obsidian-vault",
            json={
                "vault_path": str(vault_path),
                "session_limit": 10,
                "prep_limit": 10,
            },
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["counts"]["campaign_entities"] >= 3
        assert payload["counts"]["reference_documents"] == 1
        assert payload["counts"]["campaign_notes"] == 1
        assert payload["counts"]["pc_sheets"] == 1
        assert payload["counts"]["session_logs"] == 1
        assert payload["counts"]["session_prep"] == 1
        assert payload["counts"]["bases"] == 10
        assert payload["counts"]["command_center"] == 13

        npc_note = (vault_path / "Campaign/NPCs/Captain Mira.md").read_text(
            encoding="utf-8"
        )
        assert "vault_sync: true" in npc_note
        assert "entity_id:" in npc_note
        assert 'entity_type: "npc"' in npc_note
        assert (
            'current_location: "[[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]"'
            in npc_note
        )
        assert "## Overview" in npc_note
        assert "## Relationship Context" in npc_note
        assert "dma:editable:start dm-working-notes" in npc_note
        assert (
            "- `ally` with [[Campaign/PCs/Talia Stormborn|Talia Stormborn]]" in npc_note
        )

        campaign_index = (vault_path / "Campaign/Index.md").read_text(encoding="utf-8")
        assert "> [!abstract]- Campaign view" in campaign_index
        assert "![[Bases/Campaign.base]]" in campaign_index
        assert "## Browse By Type" not in campaign_index
        campaign_base = (vault_path / "Bases/Campaign.base").read_text(encoding="utf-8")
        assert "file.inFolder" in campaign_base
        assert "campaign_entity" in campaign_base

        library_index = (vault_path / "Library/Index.md").read_text(encoding="utf-8")
        assert "> [!abstract]- Reference Library Index view" in library_index
        assert "![[Bases/Library.base]]" in library_index
        assert "## Note List" not in library_index
        library_base = (vault_path / "Bases/Library.base").read_text(encoding="utf-8")
        assert 'document_kind == \\"reference\\"' in library_base
        reference_text = (
            vault_path / "Library/References/Absalom Harbor Guide.md"
        ).read_text(encoding="utf-8")
        assert 'document_kind: "reference"' in reference_text
        assert 'visibility_scope: "player_safe"' in reference_text
        assert 'audience_visibility_scope: "player_safe"' in reference_text
        assert 'audience_intended_reader: "table"' in reference_text
        assert 'source_url: "/tmp/harbor-guide.pdf"' in reference_text
        assert "## Access And Spoilers" in reference_text
        assert "## Extracted Text" in reference_text

        notes_index = (vault_path / "Notes/Index.md").read_text(encoding="utf-8")
        assert "> [!abstract]- Campaign Notes Index view" in notes_index
        assert "![[Bases/Notes.base]]" in notes_index
        assert "## Note List" not in notes_index

        note_text = (vault_path / "Notes/Port Rumors.md").read_text(encoding="utf-8")
        assert 'document_kind: "campaign_note"' in note_text
        assert "dma:editable:start editable-source" in note_text
        assert "## Linked Entities" in note_text
        assert "[[Campaign/NPCs/Captain Mira|Captain Mira]]" in note_text
        assert (
            "Summary: The docks remain tense after the fire in Greyhaven Docks."
            in note_text
        )

        sheet_index = (vault_path / "Sheets/Index.md").read_text(encoding="utf-8")
        assert "> [!abstract]- PC Sheet Index view" in sheet_index
        assert "![[Bases/Sheets.base]]" in sheet_index
        assert "## Note List" not in sheet_index
        sheets_base = (vault_path / "Bases/Sheets.base").read_text(encoding="utf-8")
        assert "pc_sheet" in sheets_base
        assert "pc_name" in sheets_base
        assert "class_dc" in sheets_base
        assert "initiative" in sheets_base
        assert "fortitude" in sheets_base
        assert "vision" in sheets_base
        assert "level" in sheets_base

        sheet_note = (vault_path / "Sheets/Talia Sheet.md").read_text(encoding="utf-8")
        assert 'document_kind: "pc_sheet"' in sheet_note
        assert 'pc_name: "Talia Stormborn"' in sheet_note
        assert "level: 4" in sheet_note
        assert "## Linked Entities" in sheet_note
        assert "## Sheet Snapshot" in sheet_note
        assert "- PC: [[Campaign/PCs/Talia Stormborn|Talia Stormborn]]" in sheet_note
        assert (
            "- Location: [[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]"
            in sheet_note
        )
        assert (
            "Relationships: contact -> [[Campaign/NPCs/Captain Mira|Captain Mira]]"
            in sheet_note
        )

        session_note = (vault_path / "Sessions/Session 12 - Harbor Fire.md").read_text(
            encoding="utf-8"
        )
        assert 'document_kind: "session_log"' in session_note
        assert "# Session 12 - Harbor Fire" in session_note
        assert "## Linked Entities" in session_note
        assert "[[Campaign/Locations/Greyhaven Docks|Greyhaven Docks]]" in session_note

        prep_note = (vault_path / "Prep/Session 13 Prep.md").read_text(encoding="utf-8")
        assert 'document_kind: "session_prep"' in prep_note
        assert prep_note.count("# Session 13 Prep") == 1
        assert "## Linked Entities" in prep_note

        start_note = (vault_path / "Command Center/Start Here.md").read_text(
            encoding="utf-8"
        )
        assert 'dma_kind: "command_center"' in start_note
        assert "[[Command Center/Session Dashboard|Session Dashboard]]" in start_note
        assert "[[Command Center/Session 1 Prep|Session 1 Prep]]" in start_note
        assert "[[Command Center/Party Overview|Party Overview]]" in start_note
        assert "[[Command Center/Session Threat Fit|Session Threat Fit]]" in start_note
        assert "[[Command Center/NPC Roster|NPC Roster]]" in start_note
        assert "Campaign entities:" in start_note

        session_dashboard = (
            vault_path / "Command Center/Session Dashboard.md"
        ).read_text(encoding="utf-8")
        assert "> [!abstract]- Current party overview" in session_dashboard
        assert "![[Bases/Party Overview.base]]" in session_dashboard
        assert "## Session Threat Fit" in session_dashboard

        party_overview = (
            vault_path / "Command Center/Party Overview.md"
        ).read_text(encoding="utf-8")
        assert "> [!abstract]- Party overview table" in party_overview
        assert "![[Bases/Party Overview.base]]" in party_overview
        assert "## Quick Assignments" in party_overview
        assert "## Coverage Snapshot" in party_overview

        threat_fit = (
            vault_path / "Command Center/Session Threat Fit.md"
        ).read_text(encoding="utf-8")
        assert "# Session Threat Fit" in threat_fit
        assert "## Fit Summary" in threat_fit
        assert "## GM Takeaways" in threat_fit

        npc_roster = (vault_path / "Command Center/NPC Roster.md").read_text(
            encoding="utf-8"
        )
        assert "> [!abstract]- NPC roster view" in npc_roster
        assert "![[Bases/NPC Roster.base]]" in npc_roster

        party_base = (vault_path / "Bases/Party Overview.base").read_text(
            encoding="utf-8"
        )
        assert "document_kind == \\\"pc_sheet\\\"" in party_base
        assert "healing_role" in party_base
        assert "scouting_role" in party_base
        assert "frontline_role" in party_base
        assert "languages" in party_base
        assert "resistances" in party_base
        assert "medicine" in party_base
        assert "special_abilities" in party_base

        location_atlas = (vault_path / "Command Center/Location Atlas.md").read_text(
            encoding="utf-8"
        )
        assert "> [!abstract]- Location atlas view" in location_atlas
        assert "![[Bases/Location Atlas.base]]" in location_atlas
    finally:
        asyncio.run(engine.dispose())


def test_obsidian_vault_import_syncs_entity_and_campaign_note_edits(tmp_path):
    app, engine, _ = create_documents_test_app()
    client = TestClient(app)

    try:
        docks = _create_entity(
            client,
            entity_type="location",
            name="Greyhaven Docks",
            details={"category": "harbor"},
        )
        npc = _create_entity(
            client,
            entity_type="npc",
            name="Captain Mira",
            current_location_id=docks["id"],
            details={"role": "harbor master", "languages": ["Common", "Varisian"]},
            tags=["harbor"],
        )
        client.post(
            "/api/campaign/import/notes",
            json={
                "title": "Port Rumors",
                "content": """
## NPC: Captain Mira
Summary: Captain Mira needs help after the dock fire.
Hooks:
- Track the saboteur.
""",
            },
        )

        vault_path = tmp_path / "vault"
        exported = client.post(
            "/api/campaign/export/obsidian-vault",
            json={"vault_path": str(vault_path)},
        )
        assert exported.status_code == 200

        npc_path = vault_path / "Campaign/NPCs/Captain Mira.md"
        npc_text = npc_path.read_text(encoding="utf-8")
        if "summary:" in npc_text:
            npc_text = re.sub(
                r'^summary:\s*".*"$',
                'summary: "Captain Mira has become the party\'s main dockside ally."',
                npc_text,
                flags=re.MULTILINE,
            )
        else:
            npc_text = npc_text.replace(
                "is_active: true\n",
                'is_active: true\nsummary: "Captain Mira has become the party\'s main dockside ally."\n',
                1,
            )
        npc_text = npc_text.replace(
            "<!-- dma:editable:start dm-working-notes -->\n\n<!-- dma:editable:end dm-working-notes -->",
            "<!-- dma:editable:start dm-working-notes -->\nCaptain Mira trusts the party with harbor security details.\n<!-- dma:editable:end dm-working-notes -->",
        )
        npc_path.write_text(npc_text, encoding="utf-8")

        note_path = vault_path / "Notes/Port Rumors.md"
        note_text = note_path.read_text(encoding="utf-8")
        note_text = note_text.replace(
            "## NPC: Captain Mira\nSummary: Captain Mira needs help after the dock fire.\nHooks:\n- Track the saboteur.",
            "## NPC: Captain Mira\nSummary: Captain Mira needs help after the dock fire.\nHooks:\n- Track the saboteur.\n- Secure witnesses before the smugglers reach them.",
        )
        note_path.write_text(note_text, encoding="utf-8")

        synced = client.post(
            "/api/campaign/import/obsidian-vault",
            json={"vault_path": str(vault_path)},
        )
        assert synced.status_code == 200
        payload = synced.json()
        assert payload["summary"]["files_synced"] >= 2

        npc_payload = client.get(f"/api/campaign/entities/{npc['id']}").json()
        assert (
            npc_payload["summary"]
            == "Captain Mira has become the party's main dockside ally."
        )
        assert (
            npc_payload["details"]["vault_dm_notes"]
            == "Captain Mira trusts the party with harbor security details."
        )

        notes = client.get("/api/documents", params={"kind": "campaign_note"}).json()[
            "items"
        ]
        note_doc = next(item for item in notes if item["title"] == "Port Rumors")
        assert (
            "Secure witnesses before the smugglers reach them." in note_doc["content"]
        )
    finally:
        asyncio.run(engine.dispose())
