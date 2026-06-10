from backend.services.live_session_service import live_session_service


def test_combat_state_normalization_preserves_afflictions():
    state = live_session_service._normalize_combat_state(
        {
            "roomId": "C11",
            "roomTitle": "Main Library",
            "round": 2,
            "activeIndex": 3,
            "combatants": [{"name": "Ghoul"}],
            "afflictions": [{"name": "Ghoul Fever", "target": "Daan"}],
        }
    )

    assert state["afflictions"] == [{"name": "Ghoul Fever", "target": "Daan"}]
    assert state["activeIndex"] == 0
