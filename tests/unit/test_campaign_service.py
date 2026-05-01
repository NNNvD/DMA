import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.models.base import Base
import backend.models.campaign  # noqa: F401
from backend.services.campaign_service import campaign_service


def test_campaign_service_generates_stable_keys_per_entity_type():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_local = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        try:
            async with session_local() as session:
                first_pc = await campaign_service.create_entity(
                    session, entity_type="pc", name="Aster"
                )
                second_pc = await campaign_service.create_entity(
                    session, entity_type="pc", name="Brin"
                )
                first_npc = await campaign_service.create_entity(
                    session, entity_type="npc", name="Captain Mira"
                )

                assert first_pc.stable_key == "PC-0001"
                assert second_pc.stable_key == "PC-0002"
                assert first_npc.stable_key == "NPC-0001"
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_campaign_service_rejects_non_location_current_location_references():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_local = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        try:
            async with session_local() as session:
                faction = await campaign_service.create_entity(
                    session, entity_type="faction", name="Lantern Guild"
                )

                try:
                    await campaign_service.create_entity(
                        session,
                        entity_type="npc",
                        name="Captain Mira",
                        current_location_id=faction.id,
                    )
                except ValueError as exc:
                    assert "Current location must reference a location or shop" in str(
                        exc
                    )
                else:
                    raise AssertionError("Expected location validation to fail")
        finally:
            await engine.dispose()

    asyncio.run(_run())
