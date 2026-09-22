#!/usr/bin/env python3
"""
Anonymize sensitive fields across fhir_legacy_bundles/ and fhir_v6/, writing
sanitized copies (mirroring the original directory layout) into
anonymized_fhir_bundles_sep22/.

Fields anonymized:
  - Full name        (Patient.name[].text, Practitioner.name[].text)
  - Address           (Patient.address -> redacted)
  - Phone numbers      (telecom entries with system == "phone")
  - Attachment URLs    (DocumentReference.content[].attachment.url, when not
                        already masked upstream)

Replacement is deterministic within a run: the same original value (same
Patient/Practitioner id, same phone number, same attachment URL) always maps
to the same placeholder, so repeat-patient linkage across files is preserved
without exposing the original PII.

Usage:
  python3 anonymize_fhir_bundles.py
"""

import json
from pathlib import Path

SOURCE_DIRS = ["fhir_legacy_bundles", "fhir_v6"]
OUTPUT_ROOT = Path("anonymized_fhir_bundles_sep22")

_name_counters: dict[str, int] = {}
_name_map: dict[tuple, str] = {}
_phone_map: dict[str, str] = {}
_phone_counter = 0
_attachment_map: dict[str, str] = {}
_attachment_counter = 0


def anon_name(resource_type: str, resource_id: str, original_text: str) -> str:
    key = (resource_type, resource_id or original_text)
    if key not in _name_map:
        _name_counters[resource_type] = _name_counters.get(resource_type, 0) + 1
        _name_map[key] = f"{resource_type.upper()}_NAME_{_name_counters[resource_type]:04d}"
    return _name_map[key]


def anon_phone(value: str) -> str:
    global _phone_counter
    if value not in _phone_map:
        _phone_counter += 1
        _phone_map[value] = f"PHONE_REDACTED_{_phone_counter:04d}"
    return _phone_map[value]


def anon_attachment_url(url: str) -> str:
    global _attachment_counter
    if url not in _attachment_map:
        _attachment_counter += 1
        ext = Path(url).suffix
        _attachment_map[url] = f"REDACTED_ATTACHMENT_{_attachment_counter:04d}{ext}"
    return _attachment_map[url]


def anonymize_resource(resource: dict) -> None:
    rtype = resource.get("resourceType")
    rid = resource.get("id")

    if rtype in ("Patient", "Practitioner"):
        for n in resource.get("name", []) or []:
            if n.get("text"):
                n["text"] = anon_name(rtype, rid, n["text"])

    if rtype == "Patient" and resource.get("address"):
        resource["address"] = [{"text": "REDACTED"} for _ in resource["address"]]

    for t in resource.get("telecom", []) or []:
        if t.get("system") == "phone" and t.get("value"):
            t["value"] = anon_phone(t["value"])

    if rtype == "DocumentReference":
        for c in resource.get("content", []) or []:
            att = c.get("attachment", {})
            url = att.get("url")
            if url and "MASKED" not in url:
                att["url"] = anon_attachment_url(url)


def process_file(src: Path, dst: Path) -> None:
    data = json.loads(src.read_text())
    entries = data.get("entry", []) if data.get("resourceType") == "Bundle" else [{"resource": data}]
    for entry in entries:
        resource = entry.get("resource")
        if resource:
            anonymize_resource(resource)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, indent=2))


def main() -> None:
    total = 0
    for src_dir in SOURCE_DIRS:
        src_root = Path(src_dir)
        for src_file in src_root.rglob("*.json"):
            rel = src_file.relative_to(src_root.parent)
            process_file(src_file, OUTPUT_ROOT / rel)
            total += 1

    print(f"Anonymized {total} files -> {OUTPUT_ROOT}")
    print(f"  Names replaced           : {sum(_name_counters.values())} ({dict(_name_counters)})")
    print(f"  Phone numbers replaced   : {_phone_counter}")
    print(f"  Attachment URLs replaced : {_attachment_counter}")


if __name__ == "__main__":
    main()
