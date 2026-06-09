#!/usr/bin/env python3
import json
import sys
import urllib.request
import urllib.error

def fetch_resource(base_url, resource_type, resource_id):
    url = f"{base_url.rstrip('/')}/{resource_type}/{resource_id}"
    req = urllib.request.Request(url, headers={"Accept": "application/fhir+json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Warning: could not fetch {resource_type}/{resource_id}: HTTP {e.code}")
        return None

def make_entry(resource):
    resource_type = resource.get("resourceType")
    resource_id = resource.get("id")
    return {
        "fullUrl": f"{resource_type}/{resource_id}",
        "resource": resource,
        "request": {
            "method": "PUT",
            "url": f"{resource_type}/{resource_id}"
        }
    }

def convert(input_path, output_path, source_base_url=None):
    with open(input_path) as f:
        bundle = json.load(f)

    if bundle.get("resourceType") != "Bundle":
        print("Error: not a FHIR Bundle")
        sys.exit(1)

    bundle["type"] = "transaction"
    bundle.pop("link", None)
    bundle.pop("total", None)
    bundle.pop("meta", None)
    bundle.pop("id", None)

    # Collect referenced subject Patient IDs
    patient_ids = set()
    for entry in bundle.get("entry", []):
        entry.pop("search", None)
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")

        if resource_type and resource_id:
            entry["request"] = {
                "method": "PUT",
                "url": f"{resource_type}/{resource_id}"
            }
        elif resource_type:
            entry["request"] = {
                "method": "POST",
                "url": resource_type
            }

        subject_ref = resource.get("subject", {}).get("reference", "")
        if subject_ref.startswith("Patient/"):
            patient_ids.add(subject_ref.split("/")[1])

    # Prepend Patient entries fetched from source
    if patient_ids and source_base_url:
        patient_entries = []
        for pid in patient_ids:
            print(f"Fetching Patient/{pid} from {source_base_url}...")
            patient = fetch_resource(source_base_url, "Patient", pid)
            if patient:
                patient_entries.append(make_entry(patient))
        bundle["entry"] = patient_entries + bundle["entry"]
        print(f"Prepended {len(patient_entries)} Patient resource(s)")
    elif patient_ids:
        print(f"Warning: bundle references Patient IDs {patient_ids} but no --source-url provided.")
        print("Pass the source FHIR base URL as the 3rd argument to auto-fetch Patients.")

    with open(output_path, "w") as f:
        json.dump(bundle, f, indent=2)

    print(f"Converted {len(bundle.get('entry', []))} entries -> {output_path}")

if __name__ == "__main__":
    input_file  = sys.argv[1] if len(sys.argv) > 1 else "bundle.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "bundle_transaction.json"
    source_url  = sys.argv[3] if len(sys.argv) > 3 else None
    convert(input_file, output_file, source_url)
