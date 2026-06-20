"""
Static catalogue built at startup.

SNOMED codes are curated from the snomed_mapped STG files — only conditions
that are clinically appropriate as FHIR Condition.code values are included
(diseases, disorders, findings). Procedures, anatomy, lab tests, and
administrative artefacts from the STG files are excluded.

The curated set aligns exactly with the variance pools used in
generate_varianced_bundles.py, so every listed code has real patient data
in FHIR to back it.
"""

from __future__ import annotations

_RAW: dict[str, dict] = {
    "MG006A": {
        "label": "Enteric Fever",
        "description": (
            "AB-PMJAY package covering management of enteric fever (typhoid) and related "
            "febrile illnesses. Treatment includes antibiotic therapy per NHA STG guidelines."
        ),
        "procedure": "Antibiotic therapy",
        "procedure_snomed_code": "281789004",
        "pre_auth_ref": "PA-MG006A",
        "bundle_count": 125,
        "stg_file": "PS1_STG2.json",
        "snomed_codes": [
            {"code": "4834000",   "display": "Typhoid fever"},
            {"code": "302231008", "display": "Salmonella infection"},
            {"code": "7520000",   "display": "Pyrexia of unknown origin"},
            {"code": "416113008", "display": "Acute febrile illness"},
            {"code": "772154007", "display": "Suspected typhoid fever"},
        ],
    },
    "MG064A": {
        "label": "Blood Transfusion",
        "description": (
            "AB-PMJAY package covering blood transfusion procedures for haematological "
            "conditions including anaemia, haemolysis, and related disorders."
        ),
        "procedure": "Transfusion of blood product",
        "procedure_snomed_code": "116859006",
        "pre_auth_ref": "PA-MG064A",
        "bundle_count": 125,
        "stg_file": "PS1_STG3.json",
        "snomed_codes": [
            {"code": "271737000", "display": "Anemia"},
            {"code": "73320003",  "display": "Hemolysis"},
            {"code": "68600005",  "display": "Hemoglobinuria"},
            {"code": "36760000",  "display": "Hepatosplenomegaly"},
            {"code": "34436003",  "display": "Hematuria"},
            {"code": "414663001", "display": "Melena"},
        ],
    },
    "SB039A": {
        "label": "Total Knee Replacement",
        "description": (
            "AB-PMJAY package covering total knee replacement surgery for end-stage knee "
            "conditions including osteoarthritis, osteonecrosis, and joint instability."
        ),
        "procedure": "Total replacement of knee joint",
        "procedure_snomed_code": "179344006",
        "pre_auth_ref": "PA-SB039A",
        "bundle_count": 125,
        "stg_file": "PS1_STG4.json",
        "snomed_codes": [
            {"code": "239873007", "display": "Osteoarthritis of knee"},
            {"code": "239862000", "display": "Primary osteoarthritis"},
            {"code": "30989003",  "display": "Knee pain"},
            {"code": "34686004",  "display": "Osteonecrosis"},
            {"code": "239821006", "display": "Secondary arthritis"},
            {"code": "67374007",  "display": "Joint instability"},
            {"code": "274665008", "display": "Chronic intractable pain"},
        ],
    },
    "SG039C": {
        "label": "Cholecystectomy",
        "description": (
            "AB-PMJAY package covering laparoscopic and open cholecystectomy for gallbladder "
            "conditions including cholelithiasis, cholecystitis, and biliary colic."
        ),
        "procedure": "Cholecystectomy",
        "procedure_snomed_code": "174041007",
        "pre_auth_ref": "PA-SG039C",
        "bundle_count": 125,
        "stg_file": "PS1_STG1.json",
        "snomed_codes": [
            {"code": "235856003", "display": "Cholelithiasis"},
            {"code": "37389005",  "display": "Biliary colic"},
            {"code": "65275009",  "display": "Acute cholecystitis"},
            {"code": "197456007", "display": "Acute pancreatitis"},
            {"code": "82403002",  "display": "Cholangitis"},
            {"code": "266474003", "display": "Choledocholithiasis"},
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
