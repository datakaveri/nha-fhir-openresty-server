#!/usr/bin/env python3
"""
Extract all distinct conditions referenced across patient bundles.
Conditions are read from the Condition resource (code.coding) in each bundle.
"""

import json
import glob
import sys
from pathlib import Path


def extract_conditions(base_dir: str) -> dict:
    """Return {snomed_code: {code, display, packages, count}} for all bundles."""
    conditions = {}

    pattern = str(Path(base_dir) / "**" / "*.json")
    files = glob.glob(pattern, recursive=True)

    if not files:
        print(f"No JSON files found under {base_dir}", file=sys.stderr)
        return conditions

    for filepath in files:
        try:
            with open(filepath) as f:
                bundle = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: skipping {filepath}: {e}", file=sys.stderr)
            continue

        # Resolve the package ID for this bundle
        package_id = None
        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Claim":
                for insurance in resource.get("insurance", []):
                    refs = insurance.get("preAuthRef", [])
                    if refs:
                        package_id = refs[0]
                        break
                if package_id:
                    break

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") != "Condition":
                continue

            for coding in resource.get("code", {}).get("coding", []):
                code = coding.get("code")
                if not code:
                    continue

                if code not in conditions:
                    conditions[code] = {
                        "code": code,
                        "display": coding.get("display", "Unknown"),
                        "system": coding.get("system", ""),
                        "packages": set(),
                        "count": 0,
                    }
                conditions[code]["count"] += 1
                if package_id:
                    conditions[code]["packages"].add(package_id)

    return conditions


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "output_original"

    conditions = extract_conditions(base_dir)

    if not conditions:
        print("No conditions found.")
        return

    print(f"{'SNOMED Code':<15} {'Count':<8} {'Packages':<30} Display")
    print("-" * 90)
    for cond in sorted(conditions.values(), key=lambda x: x["display"]):
        packages_str = ", ".join(sorted(cond["packages"]))
        print(
            f"{cond['code']:<15} "
            f"{cond['count']:<8} "
            f"{packages_str:<30} "
            f"{cond['display']}"
        )

    print(f"\nTotal distinct conditions: {len(conditions)}")


if __name__ == "__main__":
    main()
