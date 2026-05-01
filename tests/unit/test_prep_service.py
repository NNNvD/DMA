import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.base import Base
import backend.models.campaign  # noqa: F401
import backend.models.document  # noqa: F401
from backend.services.campaign_service import campaign_service
from backend.services.ingestion_service import ingestion_service
from backend.services.prep_service import prep_service


def test_prep_service_builds_markdown_and_continuity_flags():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_local = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        try:
            async with session_local() as session:
                docks = await campaign_service.create_entity(
                    session,
                    entity_type="location",
                    name="Greyhaven Docks",
                    details={"category": "harbor"},
                )
                await campaign_service.create_entity(
                    session,
                    entity_type="shop",
                    name="Brass Lantern Outfitters",
                    current_location_id=docks.id,
                    details={
                        "category": "outfitter",
                        "stock_summary": ["Lantern oil", "Rope"],
                    },
                )
                talia = await campaign_service.create_entity(
                    session,
                    entity_type="pc",
                    name="Talia Stormborn",
                    current_location_id=docks.id,
                    details={
                        "hooks": ["Investigate the smuggler ledger"],
                        "goals": ["Protect Greyhaven"],
                    },
                )
                captain = await campaign_service.create_entity(
                    session,
                    entity_type="npc",
                    name="Captain Mira",
                    current_location_id=docks.id,
                    details={"goals": ["Rebuild Dock 7"]},
                )
                guild = await campaign_service.create_entity(
                    session,
                    entity_type="faction",
                    name="Lantern Guild",
                    details={"agenda": "Restore harbor security"},
                )
                await campaign_service.ensure_relationship(
                    session,
                    source_entity_id=talia.id,
                    target_entity_id=guild.id,
                    relationship_type="member",
                )
                await campaign_service.ensure_relationship(
                    session,
                    source_entity_id=captain.id,
                    target_entity_id=talia.id,
                    relationship_type="ally",
                )
                await campaign_service.create_entity(
                    session,
                    entity_type="artifact",
                    name="Storm Ledger",
                )
                await campaign_service.create_entity(
                    session,
                    entity_type="calendar",
                    name="Coast Reckoning",
                    details={
                        "current_date": {"year": 4726, "month": "Dawnswell", "day": 20},
                        "seasons": ["Stormtide"],
                    },
                )
                await campaign_service.create_entity(
                    session,
                    entity_type="holiday",
                    name="Night of Tides",
                    current_location_id=docks.id,
                    details={"date_label": "Dawnswell 21", "recurrence": "annual"},
                )
                await campaign_service.create_entity(
                    session,
                    entity_type="event",
                    name="Guild Tribunal",
                    summary="The guild will question captured smugglers.",
                    details={
                        "scheduled_for": "year=4726; month=Dawnswell; day=21",
                        "status": "active",
                        "consequences": [
                            "Captain Mira may expose the corrupt dockmaster."
                        ],
                    },
                )
                await campaign_service.create_entity(
                    session,
                    entity_type="event",
                    name="Missed Rendezvous",
                    details={
                        "scheduled_for": "year=4726; month=Dawnswell; day=18",
                        "status": "active",
                    },
                )
                await ingestion_service.ingest_document(
                    session,
                    title="Session 12 - Harbor Fire",
                    kind="session_log",
                    content="Dock 7 burned and the smugglers escaped into the fog.",
                    summary="Dock 7 burned during the smuggler attack.",
                )
                await campaign_service.upsert_entity(
                    session,
                    entity_type="event",
                    name="Session 12 - Harbor Fire",
                    summary="Dock 7 burned during the smuggler attack.",
                    details={
                        "timeline_position": "session-12",
                        "scheduled_for": "year=4726; month=Dawnswell; day=20",
                        "status": "resolved",
                        "consequences": [
                            "Captain Mira owes Talia a favor.",
                            "The smugglers may try to recover the ledger.",
                        ],
                    },
                )

                return await prep_service.generate_session_brief(
                    session,
                    title="Harbor Recovery Prep",
                    focus="harbor recovery",
                    current_location_id=docks.id,
                    session_count=2,
                    store_document=False,
                )
        finally:
            await engine.dispose()

    payload = asyncio.run(_run())

    assert payload["title"] == "Harbor Recovery Prep"
    assert payload["document"] is None
    assert payload["location"]["name"] == "Greyhaven Docks"
    assert payload["calendar"]["current_date"]["day"] == 20
    assert any(
        hook["text"] == "Investigate the smuggler ledger"
        for hook in payload["active_hooks"]
    )
    assert any(
        "Storm Ledger" in flag["message"] for flag in payload["continuity_flags"]
    )
    assert any(
        "Missed Rendezvous" in flag["message"] for flag in payload["continuity_flags"]
    )
    assert any(
        seed["location"]["name"] == "Greyhaven Docks"
        for seed in payload["scene_seeds"]
        if seed["location"] is not None
    )
    assert "## Recap" in payload["markdown"]
    assert "## Continuity Flags" in payload["markdown"]
    assert "Storm Ledger" in payload["markdown"]
    assert "Session 12 - Harbor Fire" in payload["markdown"]
