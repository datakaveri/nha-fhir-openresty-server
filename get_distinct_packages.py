#!/usr/bin/env python3
"""
Extract all distinct packages referenced across patient bundles.
A "package" is identified by the preAuthRef in the Claim resource
(e.g. PA-MG006A) and mapped to its treatment productOrService code/display.
"""

import json
import glob
import sys
from pathlib import Path


def extract_packages(base_dir: str) -> dict:
    """Return {package_id: {code, display, folder, bundle_count}} for all bundles."""
    packages = {}

    pattern = str(Path(base_dir) / "**" / "*.json")
    files = glob.glob(pattern, recursive=True)

    if not files:
        print(f"No JSON files found under {base_dir}", file=sys.stderr)
        return packages

    for filepath in files:
        folder = Path(filepath).parent.name
        try:
            with open(filepath) as f:
                bundle = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: skipping {filepath}: {e}", file=sys.stderr)
            continue

        pre_auth_ref = None
        product_code = None
        product_display = None

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            rtype = resource.get("resourceType")

            if rtype == "Claim":
                for insurance in resource.get("insurance", []):
                    refs = insurance.get("preAuthRef", [])
                    if refs:
                        pre_auth_ref = refs[0]

                for item in resource.get("item", []):
                    pos = item.get("productOrService", {})
                    codings = pos.get("coding", [])
                    if codings:
                        product_code = codings[0].get("code")
                        product_display = codings[0].get("display")

        if pre_auth_ref:
            if pre_auth_ref not in packages:
                packages[pre_auth_ref] = {
                    "package_id": pre_auth_ref,
                    "folder": folder,
                    "product_code": product_code,
                    "product_display": product_display,
                    "bundle_count": 0,
                }
            packages[pre_auth_ref]["bundle_count"] += 1

    return packages


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "output_original"

    packages = extract_packages(base_dir)

    if not packages:
        print("No packages found.")
        return

    print(f"{'Package ID':<15} {'Folder':<10} {'Bundle Count':<14} {'Product Code':<15} Product Display")
    print("-" * 85)
    for pkg in sorted(packages.values(), key=lambda x: x["package_id"]):
        print(
            f"{pkg['package_id']:<15} "
            f"{pkg['folder']:<10} "
            f"{pkg['bundle_count']:<14} "
            f"{pkg['product_code'] or 'N/A':<15} "
            f"{pkg['product_display'] or 'N/A'}"
        )

    print(f"\nTotal distinct packages: {len(packages)}")


if __name__ == "__main__":
    main()
