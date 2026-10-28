import copy

import pytest

from backend.services.guided_workflow_service import GuidedStore, WorkflowConflict


@pytest.fixture
def store(tmp_path):
    return GuidedStore(
        tmp_path / "workflow.sqlite3",
        {"binding": "fixture", "epoch": "one", "operator": "test"},
    )


def test_answers_resume_correct_and_retries_are_idempotent(store):
    w = store.start("session-1", "prep")
    saved = store.answer(w["id"], 1, "direction", "Town", "answer-1")
    assert saved["revision"] == 2
    assert store.answer(w["id"], 1, "direction", "Town", "answer-1") == saved
    with pytest.raises(WorkflowConflict):
        store.answer(w["id"], 1, "direction", "Changed", "answer-1")
    with pytest.raises(WorkflowConflict):
        store.answer(w["id"], 1, "direction", "Road", "answer-2")
    corrected = store.answer(w["id"], 2, "direction", "Road", "answer-2")
    reopened = GuidedStore(store.path, store.scope)
    assert reopened.read(w["id"])["answers"]["direction"] == "Road"
    assert len(corrected["history"]) == 2


def test_other_operator_epoch_and_workflow_do_not_leak(store):
    w = store.start("session-1", "debrief")
    other = GuidedStore(store.path, {**store.scope, "epoch": "two"})
    assert other.list() == []
    with pytest.raises(LookupError):
        other.read(w["id"])


def test_private_notes_never_appear_in_player_report_unless_explicitly_entered(store):
    w = store.start("session-1", "debrief")
    w = store.answer(w["id"], 1, "account", "GM SECRET: the captain is a traitor", "1")
    w = store.answer(w["id"], 2, "revealed", "The party reached the bridge.", "2")
    artifacts = store.packet(w)
    assert "traitor" in artifacts["gm_log"]
    assert "traitor" not in artifacts["player_report"]
    assert "bridge" in artifacts["player_report"]
    assert artifacts["status"] == "draft"
    assert "traitor" not in str(store.preview(w["id"])["packet"])


def test_preferences_are_scoped_explicit_and_forgettable(store):
    assert store.preferences() == {}
    store.preference("detail", "short")
    assert GuidedStore(store.path, store.scope).preferences()["detail"] == "short"
    with pytest.raises(ValueError):
        store.preference("ignore_approvals", "yes")
    store.preference("detail", None)
    assert store.preferences() == {}


def test_new_answers_invalidate_drafts_and_reminders_do_not_repeat(store):
    w = store.start("s", "prep")
    w = store.answer(w["id"], 1, "direction", "Travel", "1")
    w = store.save_draft(w["id"], 2, "runbook", "An agent proposal", "draft-1")
    assert w["drafts"]["runbook"]["status"] == "draft"
    w = store.answer(w["id"], 3, "direction", "Town", "2")
    assert w["drafts"] == {}
    assert store.remind_once(w["id"], "handoff-1")
    assert not store.remind_once(w["id"], "handoff-1")


def test_only_exact_current_player_packet_can_be_marked_reviewed(store):
    w = store.start("s", "debrief")
    w = store.answer(w["id"], 1, "revealed", "We found a bell.", "1")
    preview = store.preview(w["id"])
    store.answer(w["id"], 2, "revealed", "We found a bridge.", "2")
    with pytest.raises(WorkflowConflict):
        store.approve_report(preview)
    current = store.preview(w["id"])
    tampered = copy.deepcopy(current)
    tampered["packet"]["player_report"] = "Altered"
    with pytest.raises(WorkflowConflict):
        store.approve_report(tampered)
    store.approve_report(current)
    assert (
        store.read(w["id"])["report_approval"]["intent_hash"] == current["intent_hash"]
    )
    store.answer(w["id"], 3, "revealed", "Corrected again", "3")
    assert store.read(w["id"])["report_approval"] is None


def test_quick_mode_and_corrected_handoff_are_recoverable(store):
    from backend.services.guided_workflow_service import questions_for

    w = store.start("s", "debrief")
    w = store.answer(w["id"], 1, "mode", "quick", "mode")
    assert [q[0] for q in questions_for(w)] == ["account", "revealed", "intentions"]
    for key, value in [
        ("account", "An uncertain bridge encounter"),
        ("revealed", "The bridge is open"),
        ("intentions", "Return to town"),
    ]:
        w = store.answer(w["id"], w["revision"], key, value, key)
    w = store.save_draft(w["id"], w["revision"], "runbook", "Needs review", "draft")
    assert w["status"] == "draft_ready"
    assert (
        store.packet(store.read(w["id"]))["handoff"]["intentions"] == "Return to town"
    )
    assert store.packet(w)["canon"] == "unchanged"


def test_guard_change_blocks_writes_and_keeps_saved_data(store):
    w = store.start("s", "prep")

    def deny():
        raise ValueError("Binding changed")

    store.guard = deny
    with pytest.raises(ValueError, match="Binding changed"):
        store.answer(w["id"], 1, "direction", "Town", "bad")
    store.guard = None
    assert store.read(w["id"])["revision"] == 1


def test_multiple_choice_free_text_and_skip_do_not_accept_unanswered_defaults():
    from scripts.run_guided_campaign import select_answer

    assert select_answer("1, 2", ["Town", "Travel"]) == "Town; Travel"
    assert select_answer("skip", ["Town"]) == "[skipped]"
    assert select_answer("Something unusual", ["Town"]) == "Something unusual"
    with pytest.raises(ValueError):
        select_answer("", ["Town"])


def test_interview_pause_resume_and_back_preserve_corrections(store, monkeypatch):
    from scripts.run_guided_campaign import interview

    w = store.start("s", "prep")
    inputs = iter(["2", "pause"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    w, finished = interview(store, w)
    assert not finished and w["answers"]["direction"] == "Town / social play"
    inputs = iter(["back", "3", "skip", "Keep this short", "4"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    w, finished = interview(store, store.read(w["id"]))
    assert finished
    assert w["answers"]["direction"] == "Travel / exploration"
    assert w["answers"]["priorities"] == "[skipped]"


def test_native_failure_never_replaces_saved_answers(store, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from scripts import run_guided_campaign as runner

    w = store.start("s", "prep")
    w = store.answer(w["id"], 1, "direction", "Town", "a")
    monkeypatch.setattr(runner, "source_context", lambda _: {})
    monkeypatch.setattr(runner, "build_command", lambda *_: ["fixed-codex"])
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(
            returncode=1, stderr="Unavailable", stdout=""
        ),
    )
    with pytest.raises(RuntimeError, match="answers remain saved"):
        runner.draft_runbook(tmp_path / "binding.json", w, {}, None)
    assert store.read(w["id"])["answers"]["direction"] == "Town"


def test_source_change_rejects_native_draft(store, monkeypatch, tmp_path):
    from types import SimpleNamespace
    from scripts import run_guided_campaign as runner

    values = iter([{"revision": 1}, {"revision": 2}])
    monkeypatch.setattr(runner, "source_context", lambda _: next(values))
    monkeypatch.setattr(runner, "build_command", lambda *_: ["fixed-codex"])
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_a, **_k: SimpleNamespace(
            returncode=0,
            stderr="",
            stdout='{"item":{"type":"agent_message","text":"Draft"}}',
        ),
    )
    with pytest.raises(RuntimeError, match="sources changed"):
        runner.draft_runbook(
            tmp_path / "binding.json", store.start("s", "prep"), {}, None
        )
