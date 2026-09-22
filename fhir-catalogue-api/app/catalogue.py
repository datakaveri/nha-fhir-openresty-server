"""
Catalogue of AB-PMJAY packages.

Descriptive metadata (label/description/procedure) is genuinely static and
stays hardcoded here. The SNOMED code list and bundle count are NOT static —
they depend on whatever is currently loaded in FHIR, which grows over time —
so those live in Postgres (see app/db.py) and are kept current by running
refresh_catalogue.py against the live FHIR server.
"""

from __future__ import annotations

from . import db

_PACKAGE_META: dict[str, dict] = {
    "PMJAY": {
        "label": "AB-PMJAY Claims",
        "description": (
            "All AB-PMJAY claim bundles currently loaded in FHIR. Package-level "
            "scoping (Coverage.class) isn't present in this data, so every "
            "uploaded patient falls under this single catalogue entry."
        ),
        "procedure": "N/A",
        "procedure_snomed_code": "N/A",
        "pre_auth_ref": "N/A",
    },
}


def get_package_ids() -> list[str]:
    return list(_PACKAGE_META.keys())


async def get_all_packages() -> list[dict]:
    result = []
    for pkg_id, meta in _PACKAGE_META.items():
        codes = await db.fetch_snomed_codes(pkg_id)
        bundle_count = await db.fetch_bundle_count(pkg_id)
        result.append({
            "id": pkg_id,
            "label": meta["label"],
            "description": meta["description"],
            "procedure": meta["procedure"],
            "procedure_snomed_code": meta["procedure_snomed_code"],
            "pre_auth_ref": meta["pre_auth_ref"],
            "snomed_code_count": len(codes),
            "bundle_count": bundle_count,
        })
    return result


async def get_package(package_id: str) -> dict | None:
    meta = _PACKAGE_META.get(package_id.upper())
    if not meta:
        return None
    codes = await db.fetch_snomed_codes(package_id.upper())
    bundle_count = await db.fetch_bundle_count(package_id.upper())
    return {
        "id": package_id.upper(),
        **meta,
        "snomed_code_count": len(codes),
        "bundle_count": bundle_count,
    }


async def get_snomed_codes(package_id: str) -> list[dict] | None:
    if package_id.upper() not in _PACKAGE_META:
        return None
    return await db.fetch_snomed_codes(package_id.upper())


async def is_valid_snomed_for_package(package_id: str, snomed_code: str) -> bool:
    codes = await get_snomed_codes(package_id)
    if not codes:
        return False
    return any(c["code"] == snomed_code for c in codes)


async def get_snomed_display(package_id: str, snomed_code: str) -> str | None:
    codes = await get_snomed_codes(package_id)
    if not codes:
        return None
    for c in codes:
        if c["code"] == snomed_code:
            return c["display"]
    return None
