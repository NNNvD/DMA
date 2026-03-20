import asyncio
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.base import Base
from backend.models.campaign import CampaignEntity, CampaignRelationship
from backend.services.campaign_service import (
    CampaignValidationError,
    campaign_service,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "phase2"


def _create_in_memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    session_local = asyncio.run(_init())
    return engine, session_local


def test_campaign_service_upserts_without_duplicate_entity_keys():
    engine, session_local = _create_in_memory_db()

    async def _run():
        async with session_local() as session:
            first = await campaign_service.upsert_entity(
                {
                    "entity_type": "pc",
                    "entity_key": "talia-storm",
                    "name": "Talia Storm",
                    "level": 4,
                    "ancestry": "Half-Elf",
                    "character_class": "Ranger",
                    "languages": ["Common", "Elven"],
                    "notable_items": ["Stormbow"],
                },
                session,
            )
            second = await campaign_service.upsert_entity(
                {
                    "entity_type": "pc",
                    "entity_key": "talia-storm",
                    "name": "Talia Storm",
                    "level": 5,
                    "ancestry": "Half-Elf",
                    "character_class": "Ranger",
                    "languages": ["Common", "Elven", "Goblin"],
                    "notable_items": ["Stormbow", "Fogfen map"],
                },
                session,
            )
            count = (
                await session.execute(select(func.count(CampaignEntity.id)))
            ).scalar_one()
            return first, second, count

    try:
        first, second, count = asyncio.run(_run())
        assert first.entity_key == "talia-storm"
        assert second.pc_detail is not None
        assert second.pc_detail.level == 5
        assert second.pc_detail.languages == ["Common", "Elven", "Goblin"]
        assert count == 1
    finally:
        asyncio.run(engine.dispose())


def test_campaign_service_note_import_is_idempotent():
    engine, session_local = _create_in_memory_db()
    markdown = (FIXTURE_ROOT / "sample_campaign_notes.md").read_text()

    async def _run():
        async with session_local() as session:
            first = await campaign_service.import_notes(
                source_id="session-0-notes",
                markdown=markdown,
                db=session,
            )
            second = await campaign_service.import_notes(
                source_id="session-0-notes",
                markdown=markdown,
                db=session,
            )
            relationship_count = (
                await session.execute(select(func.count(CampaignRelationship.id)))
            ).scalar_one()
            return first, second, relationship_count

    try:
        first, second, relationship_count = asyncio.run(_run())
        assert first["status"] == "applied"
        assert second["status"] == "unchanged"
        assert "captain-mira" in first["entity_keys"]
        assert relationship_count == 4
    finally:
        asyncio.run(engine.dispose())


def test_campaign_service_rejects_self_links_and_reports_location_cycles():
    engine, session_local = _create_in_memory_db()

    async def _run():
        async with session_local() as session:
            await campaign_service.upsert_entity(
                {
                    "entity_type": "location",
                    "entity_key": "otari",
                    "name": "Otari",
                },
                session,
            )
            await campaign_service.upsert_entity(
                {
                    "entity_type": "location",
                    "entity_key": "fogfen",
                    "name": "Fogfen",
                },
                session,
            )

            try:
                await campaign_service.replace_outgoing_relationships(
                    "otari",
                    [
                        {
                            "target_key": "otari",
                            "target_type": "location",
                            "relationship_type": "located_in",
                        }
                    ],
                    session,
                )
            except CampaignValidationError as error:
                message = str(error)
            else:
                raise AssertionError("Expected self-link validation error")

            otari = await campaign_service.get_required_entity("otari", session)
            fogfen = await campaign_service.get_required_entity("fogfen", session)
            session.add(
                CampaignRelationship(
                    from_entity_id=otari.id,
                    to_entity_id=fogfen.id,
                    relationship_type="located_in",
                )
            )
            session.add(
                CampaignRelationship(
                    from_entity_id=fogfen.id,
                    to_entity_id=otari.id,
                    relationship_type="located_in",
                )
            )
            await session.flush()
            report = await campaign_service.get_consistency_report(session)
            return message, report

    try:
        message, report = asyncio.run(_run())
        assert "Self relationships are not allowed" in message
        assert report["ok"] is False
        assert report["forbidden_cycles"]
    finally:
        asyncio.run(engine.dispose())
