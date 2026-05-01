import csv
import json
from pathlib import Path

from backend.services.ingestion_governance import IngestionGovernanceService


def _write(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_export_artifacts_builds_sidecars_registry_and_manifests(tmp_path: Path):
    project_root = tmp_path
    imports_root = project_root / "assets" / "imports"

    _write(
        imports_root,
        "session-logs/session-01.md",
        "Summary: The party entered Otari.\n\n## Changelog\n- The mayor asked for help.\n",
    )
    _write(
        imports_root,
        "misc/pf2e-reference/raw/guide-to-pathfinder-2e-spells.txt",
        "# Spell Guide\n\nThis is a public guide with spell advice.\n",
    )
    _write(
        imports_root,
        "misc/pf2e-reference/manifest.json",
        json.dumps(
            {
                "items": [
                    {
                        "title": "Guide to Pathfinder 2e Spells",
                        "local_path": "assets/imports/misc/pf2e-reference/raw/guide-to-pathfinder-2e-spells.txt",
                        "source_url": "https://example.com/spell-guide",
                        "notes": "Spoilers possible.",
                    }
                ]
            }
        ),
    )
    proprietary_pdf = imports_root / "WotBS-CampaignGuide.pdf"
    proprietary_pdf.write_bytes(b"%PDF-1.4 test pdf")

    service = IngestionGovernanceService(project_root=project_root)
    result = service.export_artifacts(root_path=str(imports_root))

    assert result["files_seen"] == 3
    assert result["sidecars_written"] == 3
    assert result["sources_registered"] == 3
    assert result["rag_manifest_count"] == 2
    assert result["train_manifest_count"] == 0
    assert result["review_queue_count"] == 1

    session_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "session-logs"
            / "session-01.md.json"
        ).read_text(encoding="utf-8")
    )
    assert session_sidecar["source_class"] == "trainable_open"
    assert session_sidecar["privacy_scope"] == "private_local"
    assert session_sidecar["document_type"] == "session_recap"
    assert session_sidecar["rag_eligible"] is True
    assert session_sidecar["train_eligible"] is False
    assert session_sidecar["visibility_scope"] == "gm_only"

    guide_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "pf2e-reference"
            / "raw"
            / "guide-to-pathfinder-2e-spells.txt.json"
        ).read_text(encoding="utf-8")
    )
    assert guide_sidecar["source_class"] == "trainable_with_review"
    assert guide_sidecar["review_status"] == "pending"
    assert guide_sidecar["source_url"] == "https://example.com/spell-guide"
    assert guide_sidecar["contains_spoilers"] is True

    proprietary_sidecar = json.loads(
        (
            imports_root / "metadata" / "sidecars" / "WotBS-CampaignGuide.pdf.json"
        ).read_text(encoding="utf-8")
    )
    assert proprietary_sidecar["source_class"] == "retrieval_only"
    assert proprietary_sidecar["rag_eligible"] is False

    source_registry = json.loads(
        (imports_root / "metadata" / "source_registry.json").read_text(encoding="utf-8")
    )
    assert len(source_registry["sources"]) == 3

    review_queue_lines = (
        (imports_root / "metadata" / "review_queue.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert len(review_queue_lines) == 1
    assert json.loads(review_queue_lines[0])["title"] == "Guide to Pathfinder 2e Spells"

    with (imports_root / "manifests" / "rag_manifest.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rag_rows = list(csv.DictReader(handle))
    assert len(rag_rows) == 2

    with (imports_root / "manifests" / "train_manifest.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        train_rows = list(csv.DictReader(handle))
    assert train_rows == []


def test_export_artifacts_classifies_private_local_reference_and_media_buckets(
    tmp_path: Path,
):
    project_root = tmp_path
    imports_root = project_root / "assets" / "imports"

    _write(
        imports_root,
        "misc/private-local/reference/raw/player/talingarde-common-knowledge.txt",
        "Talingarde is an island kingdom.\n",
    )
    _write(
        imports_root,
        "misc/private-local/reference/raw/gm/rise-of-the-runelords/xp.txt",
        "Arjan\t47374\n",
    )
    _write(
        imports_root,
        "misc/private-local/README.md",
        "Helper readme that should not become a corpus document.\n",
    )
    media_path = (
        imports_root
        / "misc"
        / "private-local"
        / "media"
        / "way-of-the-wicked"
        / "maps"
        / "talingarde.png"
    )
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    service = IngestionGovernanceService(project_root=project_root)
    result = service.export_artifacts(root_path=str(imports_root))

    assert result["files_seen"] == 3
    assert result["rag_manifest_count"] == 2
    assert result["train_manifest_count"] == 0

    player_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "private-local"
            / "reference"
            / "raw"
            / "player"
            / "talingarde-common-knowledge.txt.json"
        ).read_text(encoding="utf-8")
    )
    assert player_sidecar["source_class"] == "private_local"
    assert player_sidecar["document_type"] == "player_guide"
    assert player_sidecar["visibility_scope"] == "player_safe"
    assert player_sidecar["rag_eligible"] is True

    gm_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "private-local"
            / "reference"
            / "raw"
            / "gm"
            / "rise-of-the-runelords"
            / "xp.txt.json"
        ).read_text(encoding="utf-8")
    )
    assert gm_sidecar["source_class"] == "private_local"
    assert gm_sidecar["document_type"] == "gm_reference"
    assert gm_sidecar["visibility_scope"] == "gm_only"
    assert gm_sidecar["rag_eligible"] is True
    assert gm_sidecar["campaign_name"] == "Rise of the Runelords"

    media_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "private-local"
            / "media"
            / "way-of-the-wicked"
            / "maps"
            / "talingarde.png.json"
        ).read_text(encoding="utf-8")
    )
    assert media_sidecar["source_class"] == "private_local"
    assert media_sidecar["visibility_scope"] == "admin_only"
    assert media_sidecar["rag_eligible"] is False
    assert not (
        imports_root
        / "metadata"
        / "sidecars"
        / "misc"
        / "private-local"
        / "README.md.json"
    ).exists()


def test_private_local_reference_pdfs_are_rag_eligible_in_active_dropzone(
    tmp_path: Path,
):
    project_root = tmp_path
    imports_root = project_root / "assets" / "imports"

    player_pdf = (
        imports_root
        / "misc"
        / "private-local"
        / "reference"
        / "raw"
        / "player"
        / "abomination-vaults"
        / "players-guide.pdf"
    )
    player_pdf.parent.mkdir(parents=True, exist_ok=True)
    player_pdf.write_bytes(b"%PDF-1.4 player pdf")

    gm_pdf = (
        imports_root
        / "misc"
        / "private-local"
        / "reference"
        / "raw"
        / "gm"
        / "abomination-vaults"
        / "ruins-of-gauntlight.pdf"
    )
    gm_pdf.parent.mkdir(parents=True, exist_ok=True)
    gm_pdf.write_bytes(b"%PDF-1.4 gm pdf")

    service = IngestionGovernanceService(project_root=project_root)
    result = service.export_artifacts(root_path=str(imports_root))

    assert result["files_seen"] == 2
    assert result["rag_manifest_count"] == 2

    player_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "private-local"
            / "reference"
            / "raw"
            / "player"
            / "abomination-vaults"
            / "players-guide.pdf.json"
        ).read_text(encoding="utf-8")
    )
    assert player_sidecar["rag_eligible"] is True
    assert player_sidecar["visibility_scope"] == "player_safe"

    gm_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "private-local"
            / "reference"
            / "raw"
            / "gm"
            / "abomination-vaults"
            / "ruins-of-gauntlight.pdf.json"
        ).read_text(encoding="utf-8")
    )
    assert gm_sidecar["rag_eligible"] is True
    assert gm_sidecar["visibility_scope"] == "gm_only"


def test_export_artifacts_classifies_aon_rules_as_retrieval_only(tmp_path: Path):
    project_root = tmp_path
    imports_root = project_root / "assets" / "imports"

    _write(
        imports_root,
        "misc/aon-rules/raw/0097-law-and-chaos.json",
        json.dumps(
            {
                "rule_id": 97,
                "title": "Law and Chaos",
                "source_url": "https://2e.aonprd.com/Rules.aspx?ID=97",
                "source_name": "Archives of Nethys Rules Index",
                "content": "Lawful characters value consistency.",
            }
        ),
    )
    _write(
        imports_root,
        "misc/aon-rules/manifest.json",
        json.dumps(
            {
                "items": [
                    {
                        "title": "Law and Chaos",
                        "local_path": "assets/imports/misc/aon-rules/raw/0097-law-and-chaos.json",
                        "source_url": "https://2e.aonprd.com/Rules.aspx?ID=97",
                        "notes": "Fetched from AoN.",
                    }
                ]
            }
        ),
    )

    service = IngestionGovernanceService(project_root=project_root)
    result = service.export_artifacts(root_path=str(imports_root))

    assert result["files_seen"] == 1
    assert result["rag_manifest_count"] == 1
    assert result["review_queue_count"] == 0

    rule_sidecar = json.loads(
        (
            imports_root
            / "metadata"
            / "sidecars"
            / "misc"
            / "aon-rules"
            / "raw"
            / "0097-law-and-chaos.json.json"
        ).read_text(encoding="utf-8")
    )
    assert rule_sidecar["source_class"] == "retrieval_only"
    assert rule_sidecar["privacy_scope"] == "public"
    assert rule_sidecar["document_type"] == "rule_page"
    assert rule_sidecar["rag_eligible"] is True
    assert rule_sidecar["train_eligible"] is False
    assert rule_sidecar["source_url"] == "https://2e.aonprd.com/Rules.aspx?ID=97"
