#!/usr/bin/env python3
"""
fhir_table.py — Pretty-print a FHIR Bundle response as a table.

Usage:
  curl ... | python3 fhir_table.py
  python3 fhir_table.py response.json
"""

import json
import sys
from tabulate import tabulate


def extract_patient(r):
    name = r.get("name", [{}])[0]
    given = " ".join(name.get("given", []))
    return {
        "id": r.get("id"),
        "name": f"{name.get('prefix', [''])[0]} {given} {name.get('family', '')}".strip(),
        "gender": r.get("gender"),
        "birthDate": r.get("birthDate"),
        "phone": next((t["value"] for t in r.get("telecom", []) if t.get("system") == "phone"), None),
        "city": next((a.get("city") for a in r.get("address", [])), None),
        "state": next((a.get("state") for a in r.get("address", [])), None),
    }


def extract_condition(r):
    code = r.get("code", {}).get("coding", [{}])[0]
    return {
        "id": r.get("id"),
        "status": r.get("clinicalStatus", {}).get("coding", [{}])[0].get("code"),
        "code": code.get("code"),
        "display": code.get("display"),
        "system": code.get("system", "").split("/")[-1],
        "patient": r.get("subject", {}).get("reference"),
        "encounter": r.get("encounter", {}).get("reference"),
    }


def extract_coverage(r):
    cls = r.get("class", [{}])[0]
    return {
        "id": r.get("id"),
        "status": r.get("status"),
        "package_code": cls.get("value"),
        "package_name": cls.get("name"),
        "beneficiary": r.get("beneficiary", {}).get("reference"),
        "payor": r.get("payor", [{}])[0].get("reference"),
    }


def extract_claim(r):
    proc = r.get("procedure", [{}])[0].get("procedureCodeableConcept", {}).get("coding", [{}])[0]
    return {
        "id": r.get("id"),
        "status": r.get("status"),
        "use": r.get("use"),
        "patient": r.get("patient", {}).get("reference"),
        "procedure": proc.get("display"),
        "preAuthRef": r.get("insurance", [{}])[0].get("preAuthRef", [""])[0],
        "created": r.get("created"),
    }


def extract_claimresponse(r):
    item = r.get("addItem", [{}])[0]
    adj = item.get("adjudication", [{}])[0]
    return {
        "id": r.get("id"),
        "status": r.get("status"),
        "outcome": r.get("outcome"),
        "preAuthRef": r.get("preAuthRef"),
        "patient": r.get("patient", {}).get("reference"),
        "service": item.get("productOrService", {}).get("coding", [{}])[0].get("display"),
        "amount": adj.get("amount", {}).get("value"),
        "currency": adj.get("amount", {}).get("currency"),
    }


def extract_encounter(r):
    return {
        "id": r.get("id"),
        "status": r.get("status"),
        "class": r.get("class", {}).get("code"),
        "type": r.get("type", [{}])[0].get("coding", [{}])[0].get("display"),
        "patient": r.get("subject", {}).get("reference"),
        "provider": r.get("serviceProvider", {}).get("display"),
        "start": r.get("period", {}).get("start"),
        "end": r.get("period", {}).get("end"),
    }


def extract_organization(r):
    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "type": r.get("type", [{}])[0].get("coding", [{}])[0].get("display"),
        "city": next((a.get("city") for a in r.get("address", [])), None),
        "phone": next((t["value"] for t in r.get("telecom", []) if t.get("system") == "phone"), None),
    }


def extract_observation(r):
    code = r.get("code", {}).get("coding", [{}])[0]
    vq = r.get("valueQuantity", {})
    return {
        "id": r.get("id"),
        "status": r.get("status"),
        "code": code.get("code"),
        "display": code.get("display"),
        "value": vq.get("value"),
        "unit": vq.get("unit"),
        "patient": r.get("subject", {}).get("reference"),
        "effectiveDateTime": r.get("effectiveDateTime"),
    }


def extract_practitioner(r):
    name = r.get("name", [{}])[0]
    given = " ".join(name.get("given", []))
    return {
        "id": r.get("id"),
        "name": f"{name.get('prefix', [''])[0]} {given} {name.get('family', '')}".strip(),
        "gender": r.get("gender"),
        "npi": next((i["value"] for i in r.get("identifier", []) if "npi" in i.get("system", "")), None),
    }


EXTRACTORS = {
    "Patient": extract_patient,
    "Condition": extract_condition,
    "Coverage": extract_coverage,
    "Claim": extract_claim,
    "ClaimResponse": extract_claimresponse,
    "Encounter": extract_encounter,
    "Organization": extract_organization,
    "Observation": extract_observation,
    "Practitioner": extract_practitioner,
}


def process(data):
    rtype = data.get("resourceType")

    # Single resource
    if rtype in EXTRACTORS:
        row = EXTRACTORS[rtype](data)
        print(f"\n=== {rtype} ===")
        print(tabulate([row], headers="keys", tablefmt="rounded_outline"))
        return

    # Bundle (searchset or transaction response)
    if rtype == "Bundle":
        entries = data.get("entry", [])
        print(f"\nBundle type: {data.get('type')}  |  Total: {data.get('total', len(entries))}\n")

        # Group by resource type
        groups = {}
        for entry in entries:
            resource = entry.get("resource") or entry.get("response", {})
            if not resource:
                continue
            rt = resource.get("resourceType")
            if rt not in groups:
                groups[rt] = []
            groups[rt].append(resource)

        for rt, resources in groups.items():
            extractor = EXTRACTORS.get(rt)
            if extractor:
                rows = [extractor(r) for r in resources]
            else:
                rows = [{"id": r.get("id"), "resourceType": rt} for r in resources]

            print(f"--- {rt} ({len(rows)}) ---")
            print(tabulate(rows, headers="keys", tablefmt="rounded_outline"))
            print()
        return

    print(f"Unsupported resourceType: {rtype}")


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    process(data)


if __name__ == "__main__":
    main()
