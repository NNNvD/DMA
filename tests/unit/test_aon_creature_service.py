from backend.services.aon_creature_service import AonCreatureIndexItem, AonCreatureService


def test_aon_creature_parser_extracts_monster_image_url():
    service = AonCreatureService()
    html = """
    <div class="main" id="main">
      <img src="Images/Monsters/Mitflit.png" />
      Mitflit Creature -1
      Fey Gremlin
      Source Monster Core
      AC 15
      HP 10
      Fort +3
      Ref +7
      Will +4
      Speed 20 feet
      Perception +4
    <div class="clear">
    """
    document = service.parse_creature_page(
        html,
        AonCreatureIndexItem(3031, "Mitflit", -1, "Monster Core", ["Fey", "Gremlin"], True),
    )
    assert document.image_url == "https://2e.aonprd.com/Images/Monsters/Mitflit.png"


def test_aon_creature_parser_extracts_structured_combat_fields():
    service = AonCreatureService()
    html = """
    <div class="main" id="main">
      Ghoul Creature 1
      Ghoul Undead
      Source Bestiary
      Perception +7, darkvision
      Languages Common, Necril
      Skills Acrobatics +7, Athletics +4, Stealth +7
      Str +1, Dex +4, Con +2, Int +1, Wis +2, Cha +2
      AC 16
      HP 20, negative healing
      Fort +5
      Ref +9
      Will +5
      Immunities death effects, disease
      Weaknesses vitality 3
      Resistances void 3
      Speed 30 feet
      Melee jaws +9, Damage 1d6+1 piercing plus ghoul fever and paralysis
      Occult Innate Spells DC 15; 1st fear; Cantrips chill touch
      Ghoul Fever (disease) Saving Throw DC 15 Fortitude
      Paralysis (incapacitation, occult) DC 15 Fortitude
    <div class="clear">
    """
    document = service.parse_creature_page(
        html,
        AonCreatureIndexItem(218, "Ghoul", 1, "Bestiary", ["Ghoul", "Undead"], False, True),
    )

    assert document.senses == "darkvision"
    assert document.languages == "Common, Necril"
    assert document.skills == ["Acrobatics +7", "Athletics +4", "Stealth +7"]
    assert document.ability_mods == {
        "str": "+1",
        "dex": "+4",
        "con": "+2",
        "int": "+1",
        "wis": "+2",
        "cha": "+2",
    }
    assert document.immunities == "death effects, disease"
    assert document.weaknesses == "vitality 3"
    assert document.resistances == "void 3"
    assert document.attacks == [
        "Melee jaws +9, Damage 1d6+1 piercing plus ghoul fever and paralysis"
    ]
    assert document.spells == ["Occult Innate Spells DC 15; 1st fear; Cantrips chill touch"]
    assert "Ghoul Fever" in document.actions[0]


def test_aon_creature_parser_normalizes_backslash_image_paths():
    service = AonCreatureService()
    assert (
        service._image_url('<img class="thumbnail" src="Images\\Monsters\\Giant_Scorpion.webp">')
        == "https://2e.aonprd.com/Images/Monsters/Giant_Scorpion.webp"
    )


def test_aon_creature_cache_without_image_url_still_loads(tmp_path):
    service = AonCreatureService(project_root=tmp_path)
    item = service.creature_index[0]
    cache_path = service._cache_path(item)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        """
        {
          "creature_id": 3031,
          "name": "Mitflit",
          "level": -1,
          "source_url": "https://2e.aonprd.com/Monsters.aspx?ID=3031&NoRedirect=1",
          "source": "Monster Core",
          "traits": ["Fey", "Gremlin"],
          "content": "Mitflit Creature -1",
          "remastered": true,
          "legacy": false,
          "ac": "15",
          "hp": "10",
          "fort": "+3",
          "ref": "+7",
          "will": "+4",
          "speed": "20 feet",
          "perception": "+4",
          "attacks": [],
          "fetched_at": "2026-05-17T00:00:00+00:00"
        }
        """.strip(),
        encoding="utf-8",
    )
    document = service.get_creature(item.creature_id)
    assert document.image_url == ""


def test_aon_creature_cache_backfills_actions_and_merges_split_damage(tmp_path):
    service = AonCreatureService(project_root=tmp_path)
    item = AonCreatureIndexItem(218, "Ghoul", 1, "Bestiary", ["Ghoul", "Undead"], False, True)
    cache_path = service._cache_path(item)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        """
        {
          "creature_id": 218,
          "name": "Ghoul",
          "level": 1,
          "source_url": "https://2e.aonprd.com/Monsters.aspx?ID=218&NoRedirect=1",
          "source": "Bestiary",
          "traits": ["Ghoul", "Undead"],
          "content": "Ghoul Creature 1\\nMelee [one-action] jaws +9 [ +4/-1 ] ( finesse ),\\nDamage 1d6+1 piercing plus ghoul fever and paralysis\\nMelee [one-action] claw +9 [ +5/+1 ] ( agile , finesse ),\\nDamage 1d4+1 slashing plus paralysis Consume Flesh [one-action] ( manipulate )\\nRequirements The ghoul is adjacent to the corpse of a creature that died within the last hour.\\nEffect The ghoul devours a chunk of the corpse and regains 1d6 Hit Points. Ghoul Fever ( disease )\\nSaving Throw Fortitude DC 15; Stage 1 carrier with no ill effect (1 day)\\nParalysis ( incapacitation , occult ) Any living, non-elf creature hit by a ghoul’s attack must succeed at a DC 15 Fortitude save.\\nSwift Leap [one-action] ( move ) The ghoul jumps up to half its Speed.",
          "remastered": false,
          "legacy": true,
          "ac": "16",
          "hp": "20",
          "fort": "+4",
          "ref": "+9",
          "will": "+5",
          "speed": "30 feet",
          "perception": "+7",
          "attacks": [
            "Melee [one-action] jaws +9 [ +4/-1 ] ( finesse ),",
            "Damage 1d6+1 piercing plus ghoul fever and paralysis",
            "Melee [one-action] claw +9 [ +5/+1 ] ( agile , finesse ),",
            "Damage 1d4+1 slashing plus paralysis Consume Flesh [one-action] ( manipulate )"
          ],
          "image_url": "",
          "fetched_at": "2026-05-17T00:00:00+00:00"
        }
        """.strip(),
        encoding="utf-8",
    )

    document = service.get_creature(item.creature_id)

    assert document.attacks == [
        "Melee [one-action] jaws +9 [ +4/-1 ] ( finesse ), Damage 1d6+1 piercing plus ghoul fever and paralysis",
        "Melee [one-action] claw +9 [ +5/+1 ] ( agile , finesse ), Damage 1d4+1 slashing plus paralysis",
    ]
    assert any(action.startswith("Consume Flesh") for action in document.actions)
    assert any(action.startswith("Ghoul Fever") for action in document.actions)
    assert any(action.startswith("Paralysis") for action in document.actions)
    assert any(action.startswith("Swift Leap") for action in document.actions)


def test_aon_creature_cache_without_image_url_backfills_when_fetch_succeeds(tmp_path, monkeypatch):
    service = AonCreatureService(project_root=tmp_path)
    item = service.creature_index[0]
    cache_path = service._cache_path(item)
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(
        """
        {
          "creature_id": 3031,
          "name": "Mitflit",
          "level": -1,
          "source_url": "https://2e.aonprd.com/Monsters.aspx?ID=3031&NoRedirect=1",
          "source": "Monster Core",
          "traits": ["Fey", "Gremlin"],
          "content": "Mitflit Creature -1",
          "remastered": true,
          "legacy": false,
          "ac": "15",
          "hp": "10",
          "fort": "+3",
          "ref": "+7",
          "will": "+4",
          "speed": "20 feet",
          "perception": "+4",
          "attacks": [],
          "fetched_at": "2026-05-17T00:00:00+00:00"
        }
        """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        service,
        "_fetch_text",
        lambda *_args, **_kwargs: """
          <img src="https://2e.aonprd.com/Images/Monsters/Mitflit.png" />
          <h1>Mitflit</h1>
          <span>AC 15</span>
        """,
    )
    document = service.get_creature(item.creature_id)
    assert document.image_url == "https://2e.aonprd.com/Images/Monsters/Mitflit.png"


def test_aon_creature_index_contains_level_three_references():
    service = AonCreatureService()
    expected = {
        110: "Barbazu",
        218: "Ghoul",
        227: "Gibbering Mouther",
        684: "Wood Golem",
        726: "Lurker In Light",
        853: "Violet Fungus",
        4391: "Mist Stalker",
    }

    indexed = {item.creature_id: item.name for item in service.creature_index}

    for creature_id, name in expected.items():
        assert indexed[creature_id] == name


def test_aon_creature_get_creature_supports_fallback_items(tmp_path, monkeypatch):
    service = AonCreatureService(project_root=tmp_path)

    monkeypatch.setattr(
        service,
        "_fetch_text",
        lambda *_args, **_kwargs: """
          <div class="main" id="main">
            Mystery Creature Creature 9
            Source Test Source
            AC 27
            HP 135
            Fort +18
            Ref +20
            Will +17
            Speed 30 feet
            Perception +19
          <div class="clear">
        """,
    )

    document = service.get_creature(
        999999,
        fallback_name="Mystery Creature",
        fallback_level=9,
        fallback_source="Test Source",
        fallback_traits=["Test"],
    )

    assert document.creature_id == 999999
    assert document.name == "Mystery Creature"
    assert document.level == 9
    assert document.ac == "27"
