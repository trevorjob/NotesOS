"""
Seed the curated school catalogue.

Reference data, not schema — so it lives here rather than in a migration. Safe to
re-run: each row is upserted on its unique normalized_name.

    cd backend && python -m scripts.seed_schools
"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.data.schools import seed_schools  # noqa: E402
from app.database import async_session_maker  # noqa: E402
from app.models.school import School  # noqa: E402


async def main() -> None:
    rows = seed_schools()
    now = datetime.utcnow()
    inserted = 0

    async with async_session_maker() as db:
        for s in rows:
            stmt = (
                insert(School)
                .values(
                    id=uuid.uuid4(),
                    name=s["name"],
                    normalized_name=s["normalized_name"],
                    country=s["country"],
                    aliases=s["aliases"],
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["normalized_name"])
            )
            result = await db.execute(stmt)
            inserted += result.rowcount or 0
        await db.commit()

    print(f"Seeded schools: {inserted} inserted, {len(rows) - inserted} already present.")


if __name__ == "__main__":
    asyncio.run(main())
