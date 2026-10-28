from backend.services.in_game_state_service import GameStateInput, in_game_state_service


CALENDARS = [
    {
        "id": 9,
        "name": "Lantern Reckoning",
        "details": {
            "weekdays": ["Emberday", "Tideday", "Bellday"],
            "months": [
                {"name": "Bloom", "days": 30, "season": "spring"},
                {"name": "Frost", "days": 30, "season": "winter"},
            ],
            "current_date": {
                "year": 12,
                "month": "Bloom",
                "day": 1,
                "weekday": "Emberday",
            },
        },
    }
]


def resolve(**changes):
    return in_game_state_service.resolve(
        GameStateInput(**changes).model_dump(), CALENDARS
    )


def test_calendar_defaults_and_custom_weekday_and_season_are_derived():
    state = resolve(location_name="Silverbridge", year=12, month="Frost", day=2)
    assert state["calendar_name"] == "Lantern Reckoning"
    assert state["weekday"] == "Tideday"
    assert state["resolved_season"] == "winter"
    assert "Frost" in state["day_label"]


def test_weather_is_stable_on_reload_and_changes_only_with_context_or_reroll():
    first = resolve(
        location_name="Docks", year=12, month="Bloom", day=1, time_of_day="morning"
    )
    again = resolve(**first["inputs"])
    assert first["weather"] == again["weather"]
    assert first["environmental_effects"] == again["environmental_effects"]
    changed = resolve(**{**first["inputs"], "time_of_day": "night"})
    assert changed["generation_key"] != first["generation_key"]
    assert "darkness" in changed["environmental_effects"].lower()
    rerolled = resolve(**{**first["inputs"], "weather_seed": 1})
    assert rerolled["generation_key"] != first["generation_key"]


def test_manual_weather_survives_context_changes_and_drives_automatic_effects():
    first = resolve(
        location_name="Docks",
        weather_mode="manual",
        weather_text="Dense fog and heavy rain",
    )
    changed = resolve(
        **{**first["inputs"], "location_name": "Old Bridge", "time_of_day": "night"}
    )
    assert changed["weather"] == "Dense fog and heavy rain"
    assert "visibility" in changed["environmental_effects"].lower()
    assert "slippery" in changed["environmental_effects"].lower()


def test_indoor_location_does_not_apply_outdoor_rain_effects():
    state = resolve(
        location_name="Library",
        location_type="indoors",
        weather_mode="manual",
        weather_text="Heavy rain",
    )
    assert "slippery" not in state["environmental_effects"].lower()
    assert "shelter" in state["environmental_effects"].lower()
    automatic = resolve(location_name="Library", location_type="indoors")
    assert "shelter" in automatic["weather"].lower()
    underground = resolve(location_name="Cellar", location_type="underground")
    assert "underground" in underground["weather"].lower()


def test_manual_effects_remain_exact_and_switching_back_restores_generation():
    state = resolve(
        location_name="Bridge",
        effects_mode="manual",
        effects_text="Magical silence; no spellcasting sounds.",
    )
    assert state["environmental_effects"] == "Magical silence; no spellcasting sounds."
    automatic = resolve(
        **{**state["inputs"], "effects_mode": "auto", "time_of_day": "night"}
    )
    assert "darkness" in automatic["environmental_effects"].lower()


def test_unknown_calendar_does_not_invent_weekday_or_season():
    state = in_game_state_service.resolve(
        GameStateInput(
            location_name="Road", month="Unknown", day=3, year=1
        ).model_dump(),
        [],
    )
    assert state["weekday"] == ""
    assert state["resolved_season"] == "unspecified"
    manual = resolve(
        month="Unknown", day=3, year=1, weekday="Customday", season="summer"
    )
    assert manual["weekday"] == "Customday"
    assert manual["resolved_season"] == "summer"


def test_empty_location_and_manual_modes_do_not_claim_generated_conditions():
    state = in_game_state_service.resolve({}, [])
    assert state["weather"] == "Set a location to generate weather."
    manual = resolve(weather_mode="manual", effects_mode="manual")
    assert manual["weather"] == "Not set"
    assert manual["environmental_effects"] == "Not set"


def test_removed_calendar_and_changed_month_length_do_not_break_snapshot_reads():
    orphan = in_game_state_service.resolve(
        {
            "calendar_id": 99,
            "calendar_name": "Lost Calendar",
            "year": 2,
            "month": "Oldmonth",
            "day": 3,
        },
        [],
        strict=False,
    )
    assert orphan["calendar_name"] == "Lost Calendar"
    assert orphan["calendar_id"] is None
    assert orphan["warnings"]
    assert orphan["weekday"] == ""
    changed = in_game_state_service.resolve(
        {"calendar_id": 9, "year": 12, "month": "Bloom", "day": 31},
        CALENDARS,
        strict=False,
    )
    assert changed["day"] == 31
    assert changed["warnings"]
