#!/usr/bin/env python3
"""
Re-derive the catalogue's SNOMED code list from a live scan of the FHIR
server and write it to Postgres (catalogue.snomed_codes / catalogue.package_meta).

The catalogue has no automatic refresh — run this whenever bundles are
added to or removed from FHIR, so /packages/{id}/snomed-codes stays in
sync with what's actually queryable.

Usage:
  python3 refresh_catalogue.py [FHIR_BASE_URL] [DATABASE_URL]

Reads FHIR_USERNAME/FHIR_PASSWORD (or CATALOGUE_FHIR_USERNAME/PASSWORD)
from the environment for FHIR auth, same convention as the other scripts
in this repo.

DATABASE_URL can also be supplied as discrete POSTGRES_HOST/PORT/DB/USER/
PASSWORD env vars instead (same names app/config.py reads) — lets this run
as a Kubernetes Job using the exact same secretKeyRef entries as the
catalogue-api Deployment, with no shell string-concatenation required.
"""

import os
import sys
import asyncio

import asyncpg
import httpx

FHIR_BASE = (sys.argv[1].rstrip("/") if len(sys.argv) > 1
             else os.environ.get("CATALOGUE_FHIR_BASE_URL", "http://localhost:8080/fhir").rstrip("/"))


def _database_url() -> str:
    if len(sys.argv) > 2:
        return sys.argv[2]
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5433")
    db = os.environ.get("POSTGRES_DB", "hapi")
    user = os.environ.get("POSTGRES_USER", "admin")
    password = os.environ.get("POSTGRES_PASSWORD", "password")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


DATABASE_URL = _database_url()

FHIR_USER = os.environ.get("FHIR_USERNAME") or os.environ.get("CATALOGUE_FHIR_USERNAME", "admin")
FHIR_PASS = os.environ.get("FHIR_PASSWORD") or os.environ.get("CATALOGUE_FHIR_PASSWORD", "password")

SNOMED_SYSTEM = "http://snomed.info/sct"
PACKAGE_ID = "PMJAY"

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


async def scan_snomed_codes(client: httpx.AsyncClient) -> dict[str, str]:
    codes: dict[str, str] = {}
    url_or_params: str | dict = {"_elements": "code", "_count": 500}

    while url_or_params:
        if isinstance(url_or_params, dict):
            r = await client.get("/Condition", params=url_or_params)
        else:
            r = await client.get(url_or_params)
        r.raise_for_status()
        bundle = r.json()

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            for coding in resource.get("code", {}).get("coding", []):
                if coding.get("system") == SNOMED_SYSTEM and coding.get("code"):
                    codes.setdefault(coding["code"], coding.get("display", ""))

        url_or_params = next(
            (link["url"] for link in bundle.get("link", []) if link.get("relation") == "next"),
            None,
        )

    return codes


async def count_patients(client: httpx.AsyncClient) -> int:
    r = await client.get("/Patient", params={"_summary": "count"})
    r.raise_for_status()
    return r.json().get("total", 0)


async def main() -> None:
    print(f"FHIR server : {FHIR_BASE}")
    print(f"Database    : {DATABASE_URL.split('@')[-1]}\n")

    async with httpx.AsyncClient(
        base_url=FHIR_BASE,
        auth=(FHIR_USER, FHIR_PASS) if FHIR_USER and FHIR_PASS else None,
        headers={"Accept": "application/fhir+json"},
        timeout=60.0,
    ) as client:
        print("Scanning Condition resources for SNOMED codes ...")
        codes = await scan_snomed_codes(client)
        print(f"  Found {len(codes)} distinct SNOMED codes")

        print("Counting patients ...")
        bundle_count = await count_patients(client)
        print(f"  {bundle_count} patients currently in FHIR")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(SCHEMA_SQL)
        async with conn.transaction():
            await conn.execute("DELETE FROM catalogue.snomed_codes WHERE package_id = $1", PACKAGE_ID)
            await conn.executemany(
                "INSERT INTO catalogue.snomed_codes (package_id, code, display) VALUES ($1, $2, $3)",
                [(PACKAGE_ID, code, display) for code, display in codes.items()],
            )
            await conn.execute(
                """
                INSERT INTO catalogue.package_meta (package_id, bundle_count, refreshed_at)
                VALUES ($1, $2, now())
                ON CONFLICT (package_id) DO UPDATE
                    SET bundle_count = EXCLUDED.bundle_count, refreshed_at = now()
                """,
                PACKAGE_ID,
                bundle_count,
            )
    finally:
        await conn.close()

    print(f"\nCatalogue refreshed: {len(codes)} SNOMED codes, bundle_count={bundle_count}")


if __name__ == "__main__":
    asyncio.run(main())
