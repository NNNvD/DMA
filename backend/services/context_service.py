from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.context import ContextEntry


class ContextService:
    async def save(self, key: str, data: Dict[str, Any], db: AsyncSession) -> ContextEntry:
        res = await db.execute(select(ContextEntry).where(ContextEntry.key == key))
        entry = res.scalar_one_or_none()
        if entry:
            entry.data = data
        else:
            entry = ContextEntry(key=key, data=data)
            db.add(entry)
        await db.flush()
        await db.commit()
        await db.refresh(entry)
        return entry

    async def load(self, key: str, db: AsyncSession) -> Optional[ContextEntry]:
        res = await db.execute(select(ContextEntry).where(ContextEntry.key == key))
        return res.scalar_one_or_none()

    async def delete(self, key: str, db: AsyncSession) -> bool:
        res = await db.execute(select(ContextEntry).where(ContextEntry.key == key))
        entry = res.scalar_one_or_none()
        if not entry:
            return False
        await db.delete(entry)
        await db.commit()
        return True


context_service = ContextService()

