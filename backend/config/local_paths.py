from __future__ import annotations

from pathlib import Path


LEGACY_PRIVATE_ROOT = Path("assets/imports/misc/private-local")
LEGACY_VAULT_ROOT = Path("obsidian-abomination-vaults-vault")
OVERLAY_PROJECT_ROOT = Path("local-private-overlay/project-root")
OVERLAY_PRIVATE_ROOT = OVERLAY_PROJECT_ROOT / LEGACY_PRIVATE_ROOT
OVERLAY_VAULT_ROOT = OVERLAY_PROJECT_ROOT / LEGACY_VAULT_ROOT


def project_path(project_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def prefer_overlay_default(
    *,
    project_root: Path,
    configured: str | Path,
    legacy_default: Path,
    overlay_default: Path,
) -> Path:
    configured_path = Path(configured).expanduser()
    resolved = project_path(project_root, configured_path)
    if configured_path.is_absolute():
        return resolved
    if configured_path != legacy_default:
        return resolved

    overlay = (project_root / overlay_default).resolve()
    if overlay.exists():
        return overlay
    return resolved


def private_data_root(project_root: Path, configured: str | Path) -> Path:
    return prefer_overlay_default(
        project_root=project_root,
        configured=configured,
        legacy_default=LEGACY_PRIVATE_ROOT,
        overlay_default=OVERLAY_PRIVATE_ROOT,
    )


def vault_root(project_root: Path, configured: str | Path) -> Path:
    return prefer_overlay_default(
        project_root=project_root,
        configured=configured,
        legacy_default=LEGACY_VAULT_ROOT,
        overlay_default=OVERLAY_VAULT_ROOT,
    )


def private_child_root(
    *,
    project_root: Path,
    configured: str | Path,
    legacy_child: Path,
) -> Path:
    return prefer_overlay_default(
        project_root=project_root,
        configured=configured,
        legacy_default=LEGACY_PRIVATE_ROOT / legacy_child,
        overlay_default=OVERLAY_PRIVATE_ROOT / legacy_child,
    )
