"""
Static catalogue built at startup.

Single package covering the whole nha_data upload: real AB-PMJAY claim
bundles no longer tag a Health Benefit Package on Coverage.class (that field
now carries a generic PMJAY plan code, same for every patient) or fall into
the old curated 7-package/STG-file model. Rather than guess at fake package
boundaries, everything currently in FHIR is exposed under one package, and
the SNOMED list below is the real, distinct set of Condition.code SNOMED
codes found across all 63 patients currently loaded on the live FHIR server
(10 earlier death-case bundles + 53 Anemia/CABG/Cataract/Dialysis/Fever/MI/
PTCA claim bundles uploaded from filled_bundles_validated/), verified live
against https://aaehackathon.nhaad.in/fhir on 2026-08-26.

This list has no automatic refresh mechanism — whenever new bundles are
uploaded to FHIR, re-derive this list from a live `Condition` scan (dedupe
`coding[]` entries where `system == "http://snomed.info/sct"`) and update it
here, or replace this static approach with a live query.
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
        "bundle_count": 63,
        "snomed_codes": [
            {"code": "4557003", "display": "Unstable angina"},
            {"code": "4834000", "display": "Typhoid fever, unspecified"},
            {"code": "5913000", "display": "Fracture of neck of femur"},
            {"code": "7520000", "display": "Fever of other or unknown origin"},
            {"code": "8666004", "display": "Supernumerary teeth"},
            {"code": "16932000", "display": "Nausea or vomiting"},
            {"code": "22253000", "display": "Pain, unspecified"},
            {"code": "25106000", "display": "Unstable angina"},
            {"code": "27885002", "display": "Complete atrioventricular block, unspecified"},
            {"code": "27942005", "display": "Shock, unspecified"},
            {"code": "29857009", "display": "Other chest pain"},
            {"code": "41339005", "display": "Presence of coronary angioplasty implant or graft"},
            {"code": "41841004", "display": "Hereditary sideroblastic anaemias"},
            {"code": "42343007", "display": "Congestive heart failure"},
            {"code": "53741008", "display": "Diseases of coronary artery, unspecified"},
            {"code": "57054005", "display": "Acute myocardial infarction, unspecified"},
            {"code": "76571007", "display": "Septic shock"},
            {"code": "84114007", "display": "Heart failure, unspecified"},
            {"code": "84757009", "display": "Epilepsy or seizures, unspecified"},
            {"code": "91302008", "display": "Sepsis"},
            {"code": "91637004", "display": "Myasthenia gravis, unspecified"},
            {"code": "105502003", "display": "Dependence on renal dialysis"},
            {"code": "127040003", "display": "Compound heterozygous sickling disorders without crisis"},
            {"code": "127295002", "display": "Traumatic brain injury"},
            {"code": "128613002", "display": "Epilepsy or seizures, unspecified"},
            {"code": "230690007", "display": "Cerebrovascular accident"},
            {"code": "234438000", "display": "Early syphilis, unspecified"},
            {"code": "271737000", "display": "Anaemias or other erythrocyte disorders, unspecified"},
            {"code": "328383001", "display": "Chronic liver disease"},
            {"code": "363346000", "display": "Unspecified malignant neoplasms of unspecified sites"},
            {"code": "389026000", "display": "Ascites"},
            {"code": "409089005", "display": "Febrile neutropenia"},
            {"code": "413439005", "display": "Acute ischaemic heart disease, unspecified"},
            {"code": "414024009", "display": "Diseases of coronary artery, unspecified"},
            {"code": "414027002", "display": "Disorder of hematopoietic structure"},
            {"code": "417357006", "display": "Compound heterozygous sickling disorders without crisis"},
            {"code": "431857002", "display": "Chronic kidney disease, stage 4"},
            {"code": "709044004", "display": "Chronic kidney disease, stage unspecified"},
            {"code": "713689002", "display": "Presence of coronary angioplasty implant or graft"},
            {"code": "1240414004", "display": "Unspecified malignant neoplasms of unspecified sites"},
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
