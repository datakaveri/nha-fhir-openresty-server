"""
Postgres-backed storage for the catalogue's SNOMED code list.

Lives in a "catalogue" schema inside the same database HAPI FHIR uses
(kept separate from HAPI's own JPA-managed tables). Populated by
refresh_catalogue.py, which re-derives the code list from a live scan of
the FHIR server — see that script for why a static, hand-maintained list
doesn't work once the server holds more than a handful of patients.
"""

from __future__ import annotations

import asyncpg

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS catalogue;

CREATE TABLE IF NOT EXISTS catalogue.snomed_codes (
    package_id TEXT NOT NULL,
    code TEXT NOT NULL,
    display TEXT NOT NULL,
    PRIMARY KEY (package_id, code)
);

CREATE TABLE IF NOT EXISTS catalogue.package_meta (
    package_id TEXT PRIMARY KEY,
    bundle_count INT NOT NULL,
    refreshed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_pool: asyncpg.Pool | None = None


async def init_pool(database_url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def close_pool() -> None:
    if _pool is not None:
        await _pool.close()


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised")
    return _pool


async def fetch_snomed_codes(package_id: str) -> list[dict]:
    rows = await get_pool().fetch(
        "SELECT code, display FROM catalogue.snomed_codes WHERE package_id = $1 ORDER BY code",
        package_id,
    )
    return [{"code": r["code"], "display": r["display"]} for r in rows]


async def fetch_bundle_count(package_id: str) -> int:
    row = await get_pool().fetchrow(
        "SELECT bundle_count FROM catalogue.package_meta WHERE package_id = $1",
        package_id,
    )
    return row["bundle_count"] if row else 0


async def replace_snomed_codes(package_id: str, codes: list[dict], bundle_count: int) -> None:
    """Used by refresh_catalogue.py to atomically swap in a freshly-derived code list."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM catalogue.snomed_codes WHERE package_id = $1", package_id)
            await conn.executemany(
                "INSERT INTO catalogue.snomed_codes (package_id, code, display) VALUES ($1, $2, $3)",
                [(package_id, c["code"], c["display"]) for c in codes],
            )
            await conn.execute(
                """
                INSERT INTO catalogue.package_meta (package_id, bundle_count, refreshed_at)
                VALUES ($1, $2, now())
                ON CONFLICT (package_id) DO UPDATE
                    SET bundle_count = EXCLUDED.bundle_count, refreshed_at = now()
                """,
                package_id,
                bundle_count,
            )
