from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import backend.models.chunk  # noqa: F401
from backend.models.document import Document
from backend.services.obsidian_vault_service import ObsidianVaultService


def test_significant_pdf_image_specs_filters_small_images_and_smasks(monkeypatch):
    service = ObsidianVaultService()

    sample_output = """page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
--------------------------------------------------------------------------------------------
   1     0 image     902  1162  rgb     3   8  jpeg   no      2419  0   106   107 86.5K 2.8%
   1     1 smask     750   573  gray    1   8  image  no      2449  0   150   150 14.8K 3.5%
   2     2 image     120    90  rgb     3   8  jpeg   no         7  0   108   108  12K 1.4%
   3     3 image     440   300  rgb     3   8  jpeg   no        47  0   150   150 52.0K 5.5%
"""

    def fake_run(*args, **kwargs):
        return CompletedProcess(args=args[0], returncode=0, stdout=sample_output)

    monkeypatch.setattr(
        "backend.services.obsidian_vault_service.subprocess.run", fake_run
    )

    specs = service._significant_pdf_image_specs(Path("/tmp/example.pdf"))

    assert specs == [
        {"page": 1, "num": 0, "width": 902, "height": 1162},
        {"page": 3, "num": 3, "width": 440, "height": 300},
    ]


def test_significant_pdf_image_specs_uses_cache(monkeypatch):
    service = ObsidianVaultService()
    calls = 0
    sample_output = """page   num  type   width height color comp bpc  enc interp  object ID x-ppi y-ppi size ratio
--------------------------------------------------------------------------------------------
   1     0 image     902  1162  rgb     3   8  jpeg   no      2419  0   106   107 86.5K 2.8%
"""

    def fake_run(*args, **kwargs):
        nonlocal calls
        calls += 1
        return CompletedProcess(args=args[0], returncode=0, stdout=sample_output)

    monkeypatch.setattr(
        "backend.services.obsidian_vault_service.subprocess.run", fake_run
    )

    first = service._significant_pdf_image_specs(Path("/tmp/example.pdf"))
    second = service._significant_pdf_image_specs(Path("/tmp/example.pdf"))

    assert first == second == [{"page": 1, "num": 0, "width": 902, "height": 1162}]
    assert calls == 1


def test_reference_index_entries_capture_area_context_and_labels():
    service = ObsidianVaultService()

    body = """
CHAPTER 1: DECAYING GARDENS
A3. HAZY SHRINE                                    LOW 8
Creatures: Six Cult of Urthagul calignis meditate here.
They rise to attack when disturbed.
Treasure: A hero searching through this room uncovers three beautiful amethysts worth 20 gp each.
"""

    encounters = service._reference_index_entries(
        body,
        labels={"creatures", "creature", "hazards", "hazard"},
        audience="dm_only",
    )
    treasure = service._reference_index_entries(
        body,
        labels={"treasure", "story award"},
        audience="dm_only",
    )

    assert encounters == [
        {
            "kind": "encounter",
            "subtype": "monster",
            "chapter": "Decaying Gardens",
            "area": "A3",
            "title": "Hazy Shrine",
            "details": "Six Cult of Urthagul calignis meditate here. They rise to attack when disturbed.",
            "audience": "dm_only",
        }
    ]
    assert treasure == [
        {
            "kind": "treasure",
            "subtype": "treasure",
            "chapter": "Decaying Gardens",
            "area": "A3",
            "title": "Hazy Shrine",
            "details": "A hero searching through this room uncovers three beautiful amethysts worth 20 gp each.",
            "audience": "dm_only",
        }
    ]


def test_reference_index_entries_ignore_toc_noise_and_clean_area_titles():
    service = ObsidianVaultService()

    body = """
CHAPTER 1: A LIGHT IN THE FOG ................................. 4                 IN THE VAULTS
                           CHAPTER 1:
                       A Light in the Fog
A3. SLURK POND                                         LOW 1                                                                          Gazetteer
   Creatures: A single slurk guards this pond.
It spits at intruders from the water.
A4. STORAGE                                            MODERATE 1         Chapter 1:
   Treasure: Searching the crates reveals a peridot bead worth 5 gp. Adventure Toolbox
"""

    encounters = service._reference_index_entries(
        body,
        labels={"creatures", "creature", "hazards", "hazard"},
        audience="dm_only",
    )
    treasure = service._reference_index_entries(
        body,
        labels={"treasure", "story award"},
        audience="dm_only",
    )

    assert encounters == [
        {
            "kind": "encounter",
            "subtype": "monster",
            "chapter": "A Light In The Fog",
            "area": "A3",
            "title": "Slurk Pond",
            "details": "A single slurk guards this pond. It spits at intruders from the water.",
            "audience": "dm_only",
        }
    ]
    assert treasure == [
        {
            "kind": "treasure",
            "subtype": "treasure",
            "chapter": "A Light In The Fog",
            "area": "A4",
            "title": "Storage",
            "details": "Searching the crates reveals a peridot bead worth 5 gp.",
            "audience": "dm_only",
        }
    ]


def test_reference_index_entries_classify_monsters_traps_and_haunts():
    service = ObsidianVaultService()

    body = """
CHAPTER 2: TEST CHAPTER
B10. WATCH POST
Creatures: Two morlocks attack intruders from cover.
B11. BLADE HALL
Hazards: A scythe trap triggers when a creature crosses the threshold.
B12. ECHO CHAMBER
Hazards: A haunting ghostly wail erupts when someone disturbs the shrine.
"""

    encounters = service._reference_index_entries(
        body,
        labels={"creatures", "creature", "hazards", "hazard"},
        audience="dm_only",
    )

    assert encounters == [
        {
            "kind": "encounter",
            "subtype": "monster",
            "chapter": "Test Chapter",
            "area": "B10",
            "title": "Watch Post",
            "details": "Two morlocks attack intruders from cover.",
            "audience": "dm_only",
        },
        {
            "kind": "hazard",
            "subtype": "trap",
            "chapter": "Test Chapter",
            "area": "B11",
            "title": "Blade Hall",
            "details": "A scythe trap triggers when a creature crosses the threshold.",
            "audience": "dm_only",
        },
        {
            "kind": "hazard",
            "subtype": "haunt",
            "chapter": "Test Chapter",
            "area": "B12",
            "title": "Echo Chamber",
            "details": "A haunting ghostly wail erupts when someone disturbs the shrine.",
            "audience": "dm_only",
        },
    ]


def test_reference_book_number_parses_abomination_vault_titles():
    service = ObsidianVaultService()

    assert (
        service._reference_book_number("Abomination Vaults 2 Hands Of The Devil") == 2
    )
    assert service._reference_book_number("Abomination Vaults Players Guide") is None


def test_document_excerpt_for_entity_includes_pdf_page_number():
    service = ObsidianVaultService()
    document = Document(
        kind="reference",
        title="Example PDF",
        content=(
            "[Page 1]\nOpening material.\n\n"
            "[Page 2]\nWrin Sivinxi explains the danger around Gauntlight.\n"
        ),
        source_name="misc/private-local/reference/raw/gm/example.pdf",
        url="/tmp/example.pdf",
        source_class="private_local",
        privacy_scope="private_local",
        review_status="approved",
        visibility_scope="gm_only",
        rag_eligible=True,
        train_eligible=False,
    )

    excerpt = service._document_excerpt_for_entity(document, "Wrin Sivinxi")

    assert excerpt is not None
    assert excerpt["page"] == 2
    assert "Wrin Sivinxi explains the danger around Gauntlight." in excerpt["excerpt"]


def test_reference_asset_for_page_returns_first_expected_image(monkeypatch, tmp_path):
    service = ObsidianVaultService()
    source_pdf = tmp_path / "example.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    document = Document(
        kind="reference",
        title="Example PDF",
        content="",
        source_name="misc/private-local/reference/raw/gm/example.pdf",
        url=str(source_pdf),
        source_class="private_local",
        privacy_scope="private_local",
        review_status="approved",
        visibility_scope="gm_only",
        rag_eligible=True,
        train_eligible=False,
    )

    monkeypatch.setattr(
        service,
        "_significant_pdf_image_specs",
        lambda source_path: [{"page": 2, "num": 0, "width": 900, "height": 1000}],
    )

    asset_path = service._reference_asset_for_page(document, page=2)

    assert asset_path == Path("Library/Assets/Example PDF/page-002-image-01.png")


def test_document_image_link_prefers_extracted_asset():
    service = ObsidianVaultService()

    image_link = service._document_image_link(
        extracted_assets=[Path("Library/Assets/Example/page-002-image-01.png")],
        related_map_assets=[Path("Library/Assets/Maps/Book 1/Level1.jpg")],
    )

    assert image_link == "[[Library/Assets/Example/page-002-image-01.png]]"


def test_vault_guide_note_links_new_users_to_command_center():
    service = ObsidianVaultService()

    note = service._vault_guide_note()

    assert "# How To Use This Vault" in note
    assert "[[Command Center/Start Here|Command Center/Start Here]]" in note
    assert "[[Campaign/Index|Campaign/Index]]" in note
    assert "imageLink" in note


def test_document_export_title_uses_source_filename_for_pc_sheets():
    service = ObsidianVaultService()
    document = Document(
        kind="pc_sheet",
        title="Bonesy McBoner Pathbuilder Export",
        content="",
        source_name="pathbuilder/abomination-vaults/Daan.json",
        url="/tmp/Daan.json",
        source_class="private_local",
        privacy_scope="private_local",
        review_status="approved",
        visibility_scope="gm_only",
        rag_eligible=True,
        train_eligible=False,
    )

    assert service._document_export_title(document) == "Daan"


def test_sheet_snapshot_lines_include_abilities_and_defenses():
    service = ObsidianVaultService()
    entity = {
        "id": 1,
        "name": "Bonesy McBoner",
        "entity_type": "pc",
        "stable_key": "PC-0001",
        "latest_sheet_version": {
            "version_number": 1,
            "payload": {
                "class_name": "Cleric",
                "level": 1,
                "ancestry": "Skeleton",
                "heritage": "Sturdy Skeleton",
                "background": "Battlefield Scrounger",
                "attributes": {
                    "str": 14,
                    "dex": 14,
                    "con": 12,
                    "int": 8,
                    "wis": 18,
                    "cha": 12,
                },
                "ac": {"acTotal": 18, "shieldBonus": "2"},
                "proficiencies": {
                    "perception": 2,
                    "fortitude": 4,
                    "reflex": 2,
                    "will": 4,
                },
                "skills": ["Crafting", "Medicine", "Nature", "Religion", "Survival"],
            },
        },
        "relationships": [],
        "current_location": None,
    }

    lines = service._sheet_snapshot_lines(entity, {})
    joined = "\n".join(lines)

    assert "Ability Scores: STR 14, DEX 14, CON 12, INT 8, WIS 18, CHA 12" in joined
    assert "Core Defenses: AC 18, Shield 2, Perception 2, Initiative 2" in joined
    assert "Saves: Fort 4, Ref 2, Will 4" in joined


def test_sheet_vision_prefers_darkvision_over_low_light():
    service = ObsidianVaultService()

    assert service._sheet_vision({"specials": ["Low-Light Vision"]}) == "Low-Light Vision"
    assert service._sheet_vision({"specials": ["Darkvision", "Low-Light Vision"]}) == "Darkvision"


def test_sheet_role_helpers_classify_common_pf2e_party_jobs():
    service = ObsidianVaultService()

    cleric_payload = {
        "class_name": "Cleric",
        "specials": ["Low-Light Vision"],
        "ac": {"acTotal": 18},
        "proficiencies": {
            "medicine": 2,
            "stealth": 0,
            "perception": 2,
            "fortitude": 4,
        },
    }
    rogue_payload = {
        "class_name": "Rogue",
        "specials": ["Low-Light Vision"],
        "ac": {"acTotal": 17},
        "proficiencies": {
            "medicine": 2,
            "stealth": 2,
            "perception": 4,
            "fortitude": 2,
        },
    }
    guardian_payload = {
        "class_name": "Guardian",
        "specials": ["Darkvision"],
        "ac": {"acTotal": 18},
        "proficiencies": {
            "medicine": 2,
            "stealth": 0,
            "perception": 2,
            "fortitude": 4,
        },
    }

    assert service._sheet_healing_role(cleric_payload) == "Primary"
    assert service._sheet_scouting_role(rogue_payload) == "Primary"
    assert service._sheet_frontline_role(guardian_payload) == "Primary"
