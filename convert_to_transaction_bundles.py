#!/usr/bin/env python3
"""
Convert the anonymized searchset/collection bundles in
anonymized_fhir_bundles_sep22/ into FHIR transaction bundles ready to POST
to a server, writing them to converted_anonymized_fhir_bundles_sep22/
(same relative layout).

fhir_legacy_bundles/*/*.json are HAPI searchset pages: fullUrl points at the
old server and entries carry a "search" element instead of "request". Each
entry is rewritten to a relative fullUrl + PUT request keyed by the
resource's own id (references between resources already use relative
"ResourceType/id" form, so no reference rewriting is needed).

fhir_v6/*.json are "collection" bundles whose entries already use
"urn:uuid:<id>" fullUrls matching every internal reference. They only need
the bundle type switched to "transaction" and a PUT request added per
entry — the existing fullUrl/reference scheme is left untouched so HAPI's
transaction-local reference resolution keeps working.

Usage:
  python3 convert_to_transaction_bundles.py
"""

import json
import re
from pathlib import Path

SOURCE_ROOT = Path("anonymized_fhir_bundles_sep22")
OUTPUT_ROOT = Path("converted_anonymized_fhir_bundles_sep22")

# HAPI rejects client-assigned ids that are purely numeric (they'd collide
# with server-assigned sequential ids), so purely-numeric legacy ids get a
# non-numeric prefix. This regex catches "ResourceType/<numeric-id>"
# references anywhere in a resource so they stay in sync.
NUMERIC_REF = re.compile(r"^([A-Za-z]+)/([0-9]+)$")


def rewrite_numeric_refs(obj) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "reference" and isinstance(v, str):
                m = NUMERIC_REF.match(v)
                if m:
                    obj[k] = f"{m.group(1)}/legacy-{m.group(2)}"
            else:
                rewrite_numeric_refs(v)
    elif isinstance(obj, list):
        for item in obj:
            rewrite_numeric_refs(item)


def dedupe_by_full_url(bundle: dict) -> None:
    """Drop exact-duplicate entries (same fullUrl) some source files contain,
    which would otherwise make HAPI reject the transaction with
    'multiple resources with ID: <fullUrl>'."""
    seen = set()
    deduped = []
    for entry in bundle.get("entry", []):
        full_url = entry.get("fullUrl")
        if full_url in seen:
            continue
        seen.add(full_url)
        deduped.append(entry)
    bundle["entry"] = deduped


def convert_legacy_bundle(bundle: dict) -> None:
    bundle["type"] = "transaction"
    bundle.pop("total", None)
    bundle.pop("link", None)
    bundle.pop("meta", None)
    bundle.pop("id", None)
    dedupe_by_full_url(bundle)

    for entry in bundle.get("entry", []):
        entry.pop("search", None)
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        if rid and rid.isdigit():
            rid = f"legacy-{rid}"
            resource["id"] = rid
        rewrite_numeric_refs(resource)
        entry["fullUrl"] = f"{rtype}/{rid}"
        entry["request"] = {"method": "PUT", "url": f"{rtype}/{rid}"}


def convert_v6_bundle(bundle: dict) -> None:
    bundle["type"] = "transaction"
    dedupe_by_full_url(bundle)

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        entry["request"] = {"method": "PUT", "url": f"{rtype}/{rid}"}


def main() -> None:
    total = 0

    legacy_files = sorted((SOURCE_ROOT / "fhir_legacy_bundles").rglob("*.json"))
    for src in legacy_files:
        bundle = json.loads(src.read_text())
        convert_legacy_bundle(bundle)
        dst = OUTPUT_ROOT / src.relative_to(SOURCE_ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(bundle, indent=2))
        total += 1

    v6_files = sorted((SOURCE_ROOT / "fhir_v6").glob("*.json"))
    for src in v6_files:
        bundle = json.loads(src.read_text())
        convert_v6_bundle(bundle)
        dst = OUTPUT_ROOT / src.relative_to(SOURCE_ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(bundle, indent=2))
        total += 1

    print(f"Converted {len(legacy_files)} fhir_legacy_bundles files and {len(v6_files)} fhir_v6 files")
    print(f"-> {OUTPUT_ROOT} ({total} total)")


if __name__ == "__main__":
    main()
