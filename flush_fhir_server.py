#!/usr/bin/env python3
"""
Flush all resources from a HAPI FHIR server.

Strategy:
  1. POST /fhir/$expunge with expungeEverything=true  (HAPI-specific, fastest)
  2. If expunge is disabled, fall back to fetching all resources per type
     and deleting them individually via DELETE /fhir/<Type>/<id>.

Usage:
  python3 flush_fhir_server.py [FHIR_BASE_URL]
  e.g.  python3 flush_fhir_server.py http://localhost:8080/fhir
"""

import sys
import requests
from requests.auth import HTTPBasicAuth

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FHIR_BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8080/fhir"
AUTH = HTTPBasicAuth("admin", "password")
HEADERS = {
    "Content-Type": "application/fhir+json",
    "Accept": "application/fhir+json",
}

# Resource types present in the uploaded bundles
RESOURCE_TYPES = [
    "ClaimResponse",
    "Claim",
    "Coverage",
    "Condition",
    "Encounter",
    "Patient",
    "Practitioner",
    "Organization",
]


# ---------------------------------------------------------------------------
# Strategy 1: $expunge
# ---------------------------------------------------------------------------

def try_expunge() -> bool:
    """
    Attempt HAPI FHIR's server-level $expunge operation.
    Returns True if successful, False if not supported/enabled.
    """
    payload = {
        "resourceType": "Parameters",
        "parameter": [
            {"name": "expungeEverything", "valueBoolean": True}
        ],
    }
    url = f"{FHIR_BASE}/$expunge"
    print(f"Attempting $expunge at {url} ...")
    try:
        resp = requests.post(url, json=payload, auth=AUTH, headers=HEADERS, timeout=60)
    except requests.ConnectionError as e:
        print(f"  Connection error: {e}")
        return False

    if resp.status_code in (200, 201):
        print(f"  $expunge succeeded ({resp.status_code})")
        return True

    print(f"  $expunge returned {resp.status_code} — falling back to per-resource deletion.")
    return False


# ---------------------------------------------------------------------------
# Strategy 2: per-resource deletion
# ---------------------------------------------------------------------------

def fetch_all_ids(resource_type: str) -> list[str]:
    """Page through all resources of a given type and return their IDs."""
    ids = []
    url = f"{FHIR_BASE}/{resource_type}?_count=100&_elements=id"

    while url:
        try:
            resp = requests.get(url, auth=AUTH, headers=HEADERS, timeout=30)
        except requests.ConnectionError as e:
            print(f"    Connection error fetching {resource_type}: {e}")
            break

        if resp.status_code != 200:
            print(f"    GET {resource_type} returned {resp.status_code} — skipping.")
            break

        bundle = resp.json()
        for entry in bundle.get("entry", []):
            rid = entry.get("resource", {}).get("id")
            if rid:
                ids.append(rid)

        # Follow next page link
        url = None
        for link in bundle.get("link", []):
            if link.get("relation") == "next":
                url = link.get("url")
                break

    return ids


def delete_resource(resource_type: str, resource_id: str) -> bool:
    url = f"{FHIR_BASE}/{resource_type}/{resource_id}"
    try:
        resp = requests.delete(url, auth=AUTH, headers=HEADERS, timeout=30)
    except requests.ConnectionError as e:
        print(f"    Connection error deleting {resource_type}/{resource_id}: {e}")
        return False

    # 200/204 = deleted, 404 = already gone — both are fine
    return resp.status_code in (200, 204, 404)


def delete_all_resources() -> None:
    total_deleted = 0

    for rtype in RESOURCE_TYPES:
        print(f"\n  Fetching {rtype} resources ...")
        ids = fetch_all_ids(rtype)

        if not ids:
            print(f"    No {rtype} resources found.")
            continue

        print(f"    Found {len(ids)} — deleting ...")
        deleted = 0
        for rid in ids:
            if delete_resource(rtype, rid):
                deleted += 1
            else:
                print(f"    WARNING: failed to delete {rtype}/{rid}")

        print(f"    Deleted {deleted}/{len(ids)} {rtype} resources.")
        total_deleted += deleted

    print(f"\nTotal resources deleted: {total_deleted}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"FHIR server : {FHIR_BASE}")
    print(f"Auth        : admin / password")
    print()

    if try_expunge():
        print("\nServer flushed via $expunge.")
        return

    print("\nFalling back to per-resource deletion ...")
    delete_all_resources()
    print("\nDone.")


if __name__ == "__main__":
    main()
