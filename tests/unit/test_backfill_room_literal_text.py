from scripts.backfill_room_literal_text import (
    DEFAULT_ROOM_KEY_ROOT,
    PROJECT_ROOT,
    _is_private_write_path,
)


def test_backfill_default_is_private():
    assert _is_private_write_path(DEFAULT_ROOM_KEY_ROOT)


def test_backfill_rejects_public_repository_paths():
    assert not _is_private_write_path(PROJECT_ROOT / "docs")
    assert not _is_private_write_path(PROJECT_ROOT / "assets" / "imports" / "misc")


def test_backfill_allows_private_overlay_and_external_paths(tmp_path):
    assert _is_private_write_path(
        PROJECT_ROOT
        / "local-private-overlay"
        / "project-root"
        / "assets"
        / "imports"
        / "misc"
        / "private-local"
        / "room-keys"
    )
    assert _is_private_write_path(tmp_path / "private-room-keys")
