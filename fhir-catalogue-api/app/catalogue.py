"""
Static catalogue built at startup.

Single package covering the whole nha_data upload: real AB-PMJAY claim
bundles no longer tag a Health Benefit Package on Coverage.class (that field
now carries a generic PMJAY plan code, same for every patient) or fall into
the old curated 7-package/STG-file model. Rather than guess at fake package
boundaries, everything currently in FHIR is exposed under one package, and
the SNOMED list below is the real, distinct set of Condition.code SNOMED
codes found across all 10 uploaded death-case bundles (verified against
nha_data on 2026-08-05).
"""

from __future__ import annotations

_RAW: dict[str, dict] = {
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
        "bundle_count": 10,
        "snomed_codes": [
            {"code": "127295002", "display": "Traumatic brain injury"},
            {"code": "22253000",  "display": "Pain"},
            {"code": "230690007", "display": "Cerebrovascular accident"},
            {"code": "389026000", "display": "Ascites"},
            {"code": "409089005", "display": "Febrile neutropenia"},
            {"code": "414027002", "display": "Disorder of hematopoietic structure"},
            {"code": "42343007",  "display": "Congestive heart failure"},
            {"code": "5913000",   "display": "Fracture of neck of femur"},
            {"code": "76571007",  "display": "Septic shock"},
            {"code": "8666004",   "display": "Supernumerary teeth"},
            {"code": "91302008",  "display": "Sepsis"},
            {"code": "91637004",  "display": "Myasthenia gravis"},
        ],
    },
}


def get_all_packages() -> list[dict]:
    return [
        {
            "id": pkg_id,
            "label": meta["label"],
            "description": meta["description"],
            "procedure": meta["procedure"],
            "procedure_snomed_code": meta["procedure_snomed_code"],
            "pre_auth_ref": meta["pre_auth_ref"],
            "snomed_code_count": len(meta["snomed_codes"]),
            "bundle_count": meta["bundle_count"],
        }
        for pkg_id, meta in _RAW.items()
    ]


def get_package(package_id: str) -> dict | None:
    meta = _RAW.get(package_id.upper())
    if not meta:
        return None
    return {
        "id": package_id.upper(),
        **{k: v for k, v in meta.items() if k != "stg_file"},
        "snomed_code_count": len(meta["snomed_codes"]),
    }


def get_snomed_codes(package_id: str) -> list[dict] | None:
    meta = _RAW.get(package_id.upper())
    if not meta:
        return None
    return meta["snomed_codes"]


def is_valid_snomed_for_package(package_id: str, snomed_code: str) -> bool:
    codes = get_snomed_codes(package_id)
    if not codes:
        return False
    return any(c["code"] == snomed_code for c in codes)


def get_snomed_display(package_id: str, snomed_code: str) -> str | None:
    codes = get_snomed_codes(package_id)
    if not codes:
        return None
    for c in codes:
        if c["code"] == snomed_code:
            return c["display"]
    return None
