"""Entry point to run all reference-data seeds.

Usage (inside the api container):
    python -m app.seed.run_seeds

Safe to run repeatedly — every seed is idempotent.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.seed.categories import seed_categories
from app.seed.currencies import seed_currencies

logger = logging.getLogger("expensitor.seed")


async def seed_all() -> None:
    async with AsyncSessionLocal() as session:
        currencies = await seed_currencies(session)
        categories = await seed_categories(session)
        await session.commit()
    logger.info(
        "Seeding complete: %d currencies ensured, %d system categories inserted.",
        currencies,
        categories,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(seed_all())


if __name__ == "__main__":
    main()
