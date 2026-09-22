#!/usr/bin/env python3
"""
Pull all FHIR bundles from a remote FHIR server and store them locally.

For every resource type the server's CapabilityStatement advertises, this
pages through GET /<Type>?_count=<n> and saves each raw searchset Bundle
page returned by the server, so the local copy is a faithful archive of
what the server actually returns.

Usage:
  python3 pull_fhir_bundles.py [FHIR_BASE_URL] [OUTPUT_DIR]
  e.g.  python3 pull_fhir_bundles.py https://aaehackathon.nhaad.in/fhir fhir_legacy_bundles

Auth is read from FHIR_USERNAME / FHIR_PASSWORD, falling back to
CATALOGUE_FHIR_USERNAME / CATALOGUE_FHIR_PASSWORD (as set in .env for the
prod HAPI FHIR instance).
"""

import os
import sys
import json
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

FHIR_BASE = (sys.argv[1].rstrip("/") if len(sys.argv) > 1
             else os.environ.get("CATALOGUE_FHIR_BASE_URL", "http://localhost:8080/fhir").rstrip("/"))
OUTPUT_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "fhir_legacy_bundles")

FHIR_USER = os.environ.get("FHIR_USERNAME") or os.environ.get("CATALOGUE_FHIR_USERNAME", "admin")
FHIR_PASS = os.environ.get("FHIR_PASSWORD") or os.environ.get("CATALOGUE_FHIR_PASSWORD", "password")
AUTH = HTTPBasicAuth(FHIR_USER, FHIR_PASS)
HEADERS = {
    "Accept": "application/fhir+json",
}
PAGE_SIZE = 100


def discover_resource_types() -> list[str]:
    url = f"{FHIR_BASE}/metadata"
    resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    capability = resp.json()
    rest = capability.get("rest", [{}])[0]
    return sorted(r["type"] for r in rest.get("resource", []) if r.get("type"))


def pull_resource_type(resource_type: str) -> int:
    """Page through a resource type, saving each bundle page. Returns page count saved."""
    url = f"{FHIR_BASE}/{resource_type}?_count={PAGE_SIZE}"
    page_num = 0
    saved = 0

    while url:
        try:
            resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=60)
        except requests.RequestException as e:
            print(f"    Connection error: {e}")
            break

        if resp.status_code != 200:
            print(f"    GET returned {resp.status_code} — skipping.")
            break

        bundle = resp.json()
        entries = bundle.get("entry", [])

        if page_num == 0 and not entries:
            return 0

        page_num += 1
        type_dir = OUTPUT_DIR / resource_type
        type_dir.mkdir(parents=True, exist_ok=True)
        out_path = type_dir / f"page_{page_num:04d}.fhir.json"
        out_path.write_text(json.dumps(bundle, indent=2))
        saved += 1
        print(f"    page {page_num}: {len(entries)} entries -> {out_path}")

        url = None
        for link in bundle.get("link", []):
            if link.get("relation") == "next":
                url = link.get("url")
                break

    return saved


def main() -> None:
    print(f"FHIR server : {FHIR_BASE}")
    print(f"Auth        : {FHIR_USER} / ***")
    print(f"Output dir  : {OUTPUT_DIR}\n")

    print("Discovering resource types from CapabilityStatement ...")
    resource_types = discover_resource_types()
    print(f"  {len(resource_types)} resource types advertised.\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    total_pages = 0
    types_with_data = 0

    for rtype in resource_types:
        print(f"[{rtype}]")
        pages = pull_resource_type(rtype)
        if pages:
            types_with_data += 1
            total_pages += pages
        else:
            print("    (no data)")

    print("\n===== Pull complete =====")
    print(f"  Resource types with data : {types_with_data}")
    print(f"  Bundle pages saved       : {total_pages}")
    print(f"  Stored in                : {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
