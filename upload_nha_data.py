#!/usr/bin/env python3
"""
Publish the NHA FHIR transaction bundles to the local FHIR server.

DocumentReference entries (PDF/image attachments) are stripped out before
upload — only the clinical/financial FHIR resources are pushed.

Usage:
  python3 upload_nha_data.py [FHIR_BASE_URL] [DATA_DIR]
  e.g.  python3 upload_nha_data.py http://localhost:8080/fhir nha_data
"""

import sys
import json
import glob
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth

FHIR_BASE = (sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8080/fhir")
DATA_DIR = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parent / "nha_data")
AUTH = HTTPBasicAuth("admin", "password")
HEADERS = {
    "Content-Type": "application/fhir+json",
    "Accept": "application/fhir+json",
}


def strip_document_references(bundle: dict) -> dict:
    entries = bundle.get("entry", [])

    removed_urls = {
        e.get("fullUrl")
        for e in entries
        if e.get("resource", {}).get("resourceType") == "DocumentReference"
    }

    bundle["entry"] = [
        e for e in entries
        if e.get("resource", {}).get("resourceType") != "DocumentReference"
    ]

    # Drop Claim.supportingInfo items that pointed at the removed DocumentReferences
    for e in bundle["entry"]:
        r = e.get("resource", {})
        if r.get("resourceType") == "Claim" and "supportingInfo" in r:
            r["supportingInfo"] = [
                item for item in r["supportingInfo"]
                if item.get("valueReference", {}).get("reference") not in removed_urls
            ]
            if not r["supportingInfo"]:
                del r["supportingInfo"]

    return bundle


def main() -> None:
    files = sorted(glob.glob(f"{DATA_DIR}/**/*.fhir.json", recursive=True))
    total = len(files)
    print(f"FHIR server : {FHIR_BASE}")
    print(f"Data dir    : {DATA_DIR}")
    print(f"Bundles     : {total}\n")

    success = 0
    failed = []

    for i, file in enumerate(files, 1):
        rel = Path(file).relative_to(DATA_DIR)
        print(f"[{i}/{total}] Uploading {rel} ... ", end="", flush=True)

        bundle = json.load(open(file))
        bundle = strip_document_references(bundle)

        try:
            resp = requests.post(FHIR_BASE, json=bundle, auth=AUTH, headers=HEADERS, timeout=60)
        except requests.ConnectionError as e:
            print(f"FAILED (connection error: {e})")
            failed.append(str(rel))
            continue

        if resp.status_code in (200, 201):
            print(f"OK ({resp.status_code})")
            success += 1
        else:
            print(f"FAILED ({resp.status_code})")
            print(resp.text[:1000])
            failed.append(str(rel))

    print("\n===== Upload complete =====")
    print(f"  Success: {success}")
    print(f"  Failed:  {len(failed)}")
    if failed:
        print("\nFailed files:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
