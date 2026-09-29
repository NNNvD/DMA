import asyncio
from types import SimpleNamespace

from backend.api.routes import live


def test_aon_creature_response_includes_combat_detail_fields(monkeypatch):
    creature = SimpleNamespace(
        creature_id=1040,
        name="Scalathrax",
        level=4,
        source_url="https://2e.aonprd.com/Monsters.aspx?ID=1040",
        source="Ruins of Gauntlight",
        traits=["Aberration"],
        content="Scalathrax Creature 4",
        remastered=False,
        legacy=True,
        alignment="N",
        size="Medium",
        rarity="Common",
        ac="21",
        hp="60",
        fort="+11",
        ref="+13",
        will="+9",
        speed="25 feet",
        perception="+11",
        senses="darkvision",
        languages="Undercommon",
        skills=["Stealth +13"],
        ability_mods={"dex": "+5"},
        immunities="",
        weaknesses="fire 5",
        resistances="poison 5",
        attacks=["Melee jaws +13"],
        actions=["Oily Scales: slippery scales"],
        spells=[],
        image_url="",
        fetched_at="2026-09-29T00:00:00Z",
    )
    monkeypatch.setattr(
        live.aon_creature_service, "get_creature", lambda *args, **kwargs: creature
    )
    payload = asyncio.run(
        live.get_aon_creature(
            creature_id=1040,
            refresh=False,
            name=None,
            level=None,
            source=None,
            traits=None,
        )
    )["creature"]
    assert payload["actions"] == creature.actions
    assert payload["senses"] == "darkvision"
    assert payload["weaknesses"] == "fire 5"
    assert payload["skills"] == ["Stealth +13"]
