#!/usr/bin/env python3
"""
Generate varianced FHIR bundles into output_varianced/.

For each bundle in output/ (already fixed: type=transaction, proper request entries):
  - Randomly assign a clinically appropriate condition from the SNOMED-mapped
    pool for that package (derived from snomed_mapped/NHA/PS1/).
  - The Condition resource code/text is replaced; all references remain intact.

Seeded per bundle filename for reproducibility.
"""

import json
import glob
import os
import random
import hashlib
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Condition pools per package — curated from snomed_mapped/NHA/PS1/ STG files.
# Only includes entities that are appropriate as FHIR Condition.code values
# (disorders, diseases, clinical findings), excluding procedures, tests, and
# administrative artefacts.
# ---------------------------------------------------------------------------

CONDITION_POOLS = {
    # MG006A — Enteric fever / Typhoid (PS1_STG2)
    "PA-MG006A": [
        {"code": "4834000",   "display": "Typhoid fever"},
        {"code": "302231008", "display": "Salmonella infection"},
        {"code": "7520000",   "display": "Pyrexia of unknown origin"},
        {"code": "416113008", "display": "Acute febrile illness"},
        {"code": "772154007", "display": "Suspected typhoid fever"},
    ],

    # MG064A — Blood transfusion (PS1_STG3)
    "PA-MG064A": [
        {"code": "271737000", "display": "Anemia"},
        {"code": "73320003",  "display": "Hemolysis"},
        {"code": "68600005",  "display": "Hemoglobinuria"},
        {"code": "36760000",  "display": "Hepatosplenomegaly"},
        {"code": "34436003",  "display": "Hematuria"},
        {"code": "414663001", "display": "Melena"},
    ],

    # SB039A — Total knee replacement (PS1_STG4)
    "PA-SB039A": [
        {"code": "239873007", "display": "Osteoarthritis of knee"},
        {"code": "239862000", "display": "Primary osteoarthritis"},
        {"code": "30989003",  "display": "Knee pain"},
        {"code": "34686004",  "display": "Osteonecrosis"},
        {"code": "239821006", "display": "Secondary arthritis"},
        {"code": "67374007",  "display": "Joint instability"},
        {"code": "274665008", "display": "Chronic intractable pain"},
    ],

    # SG039C — Cholecystectomy (PS1_STG1)
    "PA-SG039C": [
        {"code": "235856003", "display": "Cholelithiasis"},
        {"code": "37389005",  "display": "Biliary colic"},
        {"code": "65275009",  "display": "Acute cholecystitis"},
        {"code": "197456007", "display": "Acute pancreatitis"},
        {"code": "82403002",  "display": "Cholangitis"},
        {"code": "266474003", "display": "Choledocholithiasis"},
    ],
}


def pick_condition(package_id: str, seed: str) -> dict:
    """Deterministically pick a condition from the pool using the bundle name as seed."""
    pool = CONDITION_POOLS.get(package_id)
    if not pool:
        return None
    rng = random.Random(int(hashlib.md5(seed.encode()).hexdigest(), 16))
    return rng.choice(pool)


def get_package_id(bundle: dict) -> str | None:
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Claim":
            for insurance in resource.get("insurance", []):
                refs = insurance.get("preAuthRef", [])
                if refs:
                    return refs[0]
    return None


def apply_variance(bundle: dict, condition: dict) -> dict:
    """Replace the Condition resource code in-place and return the bundle."""
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Condition":
            resource["code"] = {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": condition["code"],
                        "display": condition["display"],
                    }
                ],
                "text": condition["display"],
            }
    return bundle


def process_bundles(input_dir: str, output_dir: str) -> None:
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    files = sorted(glob.glob(str(input_path / "**" / "*.json"), recursive=True))
    if not files:
        print(f"No JSON files found under {input_dir}")
        return

    stats: dict[str, dict] = {}
    processed = 0

    for filepath in files:
        rel = Path(filepath).relative_to(input_path)
        dest = output_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath) as f:
                bundle = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: skipping {filepath}: {e}")
            continue

        package_id = get_package_id(bundle)
        if not package_id:
            shutil.copy2(filepath, dest)
            continue

        condition = pick_condition(package_id, rel.name)
        if condition:
            bundle = apply_variance(bundle, condition)
            pkg_stats = stats.setdefault(package_id, {})
            pkg_stats[condition["display"]] = pkg_stats.get(condition["display"], 0) + 1

        with open(dest, "w") as f:
            json.dump(bundle, f, indent=2)

        processed += 1

    print(f"Processed {processed} bundles → {output_dir}\n")
    print("Condition distribution per package:")
    for pkg, dist in sorted(stats.items()):
        print(f"\n  {pkg}:")
        for cond, count in sorted(dist.items(), key=lambda x: -x[1]):
            print(f"    {count:>4}  {cond}")


if __name__ == "__main__":
    import sys

    input_dir = sys.argv[1] if len(sys.argv) > 1 else "output"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output_varianced"

    process_bundles(input_dir, output_dir)
