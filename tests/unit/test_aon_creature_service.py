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
