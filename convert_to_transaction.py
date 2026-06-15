#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

UUID_REF_RE = re.compile(r"^urn:uuid:([0-9a-f\-]+)$", re.IGNORECASE)
CONDITIONAL_REF_RE = re.compile(r"^(\w+)\?identifier=([^|]+)\|(.+)$")


def build_maps(bundle: dict) -> tuple[dict, dict]:
    """
    Returns:
      uuid_map:       bare-uuid  → ResourceType/id
      identifier_map: (ResourceType, "system|value") → ResourceType/id
    """
    uuid_map = {}
    identifier_map = {}
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rt = resource.get("resourceType")
        rid = resource.get("id")
        if not (rt and rid):
            continue
        canonical = f"{rt}/{rid}"
        uuid_map[rid] = canonical
        for ident in resource.get("identifier", []):
            system = ident.get("system", "")
            value = ident.get("value", "")
            if system and value:
                identifier_map[(rt, f"{system}|{value}")] = canonical
    return uuid_map, identifier_map


def fix_references(obj, uuid_map: dict, identifier_map: dict) -> None:
    """Recursively resolve urn:uuid and conditional search references."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "reference" and isinstance(value, str):
                m = UUID_REF_RE.match(value)
                if m:
                    uid = m.group(1)
                    if uid in uuid_map:
                        obj[key] = uuid_map[uid]
                    continue
                m = CONDITIONAL_REF_RE.match(value)
                if m:
                    rt, system, val = m.group(1), m.group(2), m.group(3)
                    resolved = identifier_map.get((rt, f"{system}|{val}"))
                    if resolved:
                        obj[key] = resolved
                    # else: unresolvable — leave for strip_unresolvable_refs to handle
            else:
                fix_references(value, uuid_map, identifier_map)
    elif isinstance(obj, list):
        for item in obj:
            fix_references(item, uuid_map, identifier_map)


def has_unresolvable_ref(obj) -> bool:
    """Return True if obj contains any conditional reference that wasn't resolved."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "reference" and isinstance(value, str) and CONDITIONAL_REF_RE.match(value):
                return True
            if has_unresolvable_ref(value):
                return True
    elif isinstance(obj, list):
        return any(has_unresolvable_ref(item) for item in obj)
    return False


def strip_unresolvable_refs(obj) -> None:
    """Remove list items that contain any unresolvable conditional reference."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            value = obj[key]
            if isinstance(value, list):
                obj[key] = [item for item in value if not has_unresolvable_ref(item)]
                for item in obj[key]:
                    strip_unresolvable_refs(item)
            else:
                strip_unresolvable_refs(value)
    elif isinstance(obj, list):
        for item in obj:
            strip_unresolvable_refs(item)


def convert_bundle(path: Path) -> None:
    with open(path) as f:
        bundle = json.load(f)

    if bundle.get("resourceType") != "Bundle":
        print(f"  SKIP {path}: not a Bundle")
        return

    bundle["type"] = "transaction"

    uuid_map, identifier_map = build_maps(bundle)
    fix_references(bundle, uuid_map, identifier_map)
    # Strip unresolvable refs within each resource (not at the bundle entry level,
    # to avoid accidentally removing whole entries)
    for entry in bundle.get("entry", []):
        if "resource" in entry:
            strip_unresolvable_refs(entry["resource"])

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rt = resource.get("resourceType")
        rid = resource.get("id")
        url = f"{rt}/{rid}" if rt and rid else entry.get("fullUrl", "")
        entry["request"] = {"method": "PUT", "url": url}

    with open(path, "w") as f:
        json.dump(bundle, f, indent=2)


def main():
    output_dir = Path(__file__).parent / "output"
    if not output_dir.exists():
        print(f"Directory not found: {output_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(output_dir.rglob("*.json"))
    print(f"Converting {len(files)} bundles...")

    for path in files:
        print(f"  {path.relative_to(output_dir)}")
        convert_bundle(path)

    print("Done.")


if __name__ == "__main__":
    main()
