"""
Async FHIR client wrapping httpx.

All FHIR queries go through this module. Results that are expensive to
re-fetch (patient ID lists per package, per-code counts) are cached
in-process with a configurable TTL.
"""

from __future__ import annotations

import time
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SNOMED_SYSTEM = "http://snomed.info/sct"


class _TTLCache:
    def __init__(self, ttl: int) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry and (time.monotonic() - entry[0]) < self._ttl:
            return entry[1]
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic(), value)


class FHIRClient:
    def __init__(self, base_url: str, username: str = "", password: str = "", cache_ttl: int = 300) -> None:
        auth = (username, password) if username and password else None
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=auth,
            headers={
                "Accept": "application/fhir+json",
                "Content-Type": "application/fhir+json",
            },
            timeout=30.0,
        )
        self._cache = _TTLCache(cache_ttl)

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        try:
            r = await self._client.get("/metadata", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Package → Patient IDs  (cached)
    # ------------------------------------------------------------------

    async def get_patient_ids_for_package(self, package_code: str) -> list[str]:
        cache_key = f"patient_ids:{package_code}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        ids: list[str] = []
        url = f"/Coverage?class-value={package_code}&_elements=subscriber&_count=500"
        error_occurred = False

        while url:
            try:
                r = await self._client.get(url)
                r.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("FHIR Coverage query failed: %s", exc)
                error_occurred = True
                break

            bundle = r.json()
            for entry in bundle.get("entry", []):
                ref = entry.get("resource", {}).get("subscriber", {}).get("reference", "")
                # ref looks like "Patient/<uuid>"
                if ref.startswith("Patient/"):
                    ids.append(ref.split("/", 1)[1])

            url = _next_link(bundle)

        if not error_occurred:
            self._cache.set(cache_key, ids)
        return ids

    # ------------------------------------------------------------------
    # SNOMED condition count (cached)
    # ------------------------------------------------------------------

    async def get_condition_count(self, package_code: str, snomed_code: str) -> int | None:
        cache_key = f"count:{package_code}:{snomed_code}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        patient_ids = await self.get_patient_ids_for_package(package_code)
        if not patient_ids:
            return 0

        # HAPI supports comma-separated subject list
        subjects = ",".join(f"Patient/{pid}" for pid in patient_ids)
        code_param = f"{SNOMED_SYSTEM}|{snomed_code}"

        try:
            r = await self._client.get(
                "/Condition",
                params={"code": code_param, "subject": subjects, "_summary": "count"},
            )
            r.raise_for_status()
            count = r.json().get("total", 0)
        except httpx.HTTPError as exc:
            logger.warning("FHIR Condition count query failed: %s", exc)
            return None

        self._cache.set(cache_key, count)
        return count

    # ------------------------------------------------------------------
    # Patient data for a package + single SNOMED code
    # ------------------------------------------------------------------

    async def get_patients(self, package_code: str, snomed_code: str) -> tuple[int, list[dict], dict]:
        """
        Returns (total, list_of_patient_records, raw_bundle).

        Two-step:
          1. Resolve patient IDs for the package via Coverage.
          2. Fetch Conditions matching the SNOMED code for those patients,
             including the linked Patient resource.
        """
        patient_ids = await self.get_patient_ids_for_package(package_code)
        if not patient_ids:
            return 0, [], _empty_bundle()

        subjects = ",".join(f"Patient/{pid}" for pid in patient_ids)
        code_param = f"{SNOMED_SYSTEM}|{snomed_code}"

        conditions: list[dict] = []
        patients_by_id: dict[str, dict] = {}
        url_or_params: str | dict = {
            "code": code_param,
            "subject": subjects,
            "_include": "Condition:subject",
            "_count": 200,
        }

        while url_or_params:
            try:
                if isinstance(url_or_params, dict):
                    r = await self._client.get("/Condition", params=url_or_params)
                else:
                    r = await self._client.get(url_or_params)
                r.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("FHIR Condition query failed: %s", exc)
                break

            bundle = r.json()
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                rtype = resource.get("resourceType")
                if rtype == "Condition":
                    conditions.append(resource)
                elif rtype == "Patient":
                    patients_by_id[resource.get("id", "")] = resource

            next_url = _next_link(bundle)
            url_or_params = next_url if next_url else None

        records = [_shape_record(cond, patients_by_id) for cond in conditions]
        records = [r for r in records if r]  # drop any that failed to shape
        return len(records), records, _build_bundle(conditions, patients_by_id)

    # ------------------------------------------------------------------
    # Patient data for a package + multiple SNOMED codes (OR logic)
    # ------------------------------------------------------------------

    async def get_patients_multi(self, package_code: str, snomed_codes: list[str]) -> tuple[int, list[dict], dict]:
        """
        Returns (total, list_of_patient_records, raw_bundle) for any patient whose
        condition matches ANY of the supplied SNOMED codes.

        FHIR represents OR as comma-separated values within one code parameter:
          code=http://snomed.info/sct|4834000,http://snomed.info/sct|302231008
        A single FHIR round-trip retrieves all matches at once.
        """
        patient_ids = await self.get_patient_ids_for_package(package_code)
        if not patient_ids:
            return 0, [], _empty_bundle()

        subjects = ",".join(f"Patient/{pid}" for pid in patient_ids)
        # FHIR OR: comma-separated token values in one parameter
        code_param = ",".join(f"{SNOMED_SYSTEM}|{code}" for code in snomed_codes)

        conditions: list[dict] = []
        patients_by_id: dict[str, dict] = {}
        url_or_params: str | dict = {
            "code": code_param,
            "subject": subjects,
            "_include": "Condition:subject",
            "_count": 500,
        }

        while url_or_params:
            try:
                if isinstance(url_or_params, dict):
                    r = await self._client.get("/Condition", params=url_or_params)
                else:
                    r = await self._client.get(url_or_params)
                r.raise_for_status()
            except httpx.HTTPError as exc:
                logger.warning("FHIR multi-code Condition query failed: %s", exc)
                break

            bundle = r.json()
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                rtype = resource.get("resourceType")
                if rtype == "Condition":
                    conditions.append(resource)
                elif rtype == "Patient":
                    patients_by_id[resource.get("id", "")] = resource

            next_url = _next_link(bundle)
            url_or_params = next_url if next_url else None

        records = [_shape_record(cond, patients_by_id) for cond in conditions]
        records = [r for r in records if r]
        return len(records), records, _build_bundle(conditions, patients_by_id)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _next_link(bundle: dict) -> str | None:
    for link in bundle.get("link", []):
        if link.get("relation") == "next":
            return link.get("url")
    return None


def _shape_record(condition: dict, patients: dict[str, dict]) -> dict | None:
    subject_ref = condition.get("subject", {}).get("reference", "")
    patient_id = subject_ref.split("/", 1)[1] if "/" in subject_ref else subject_ref
    patient = patients.get(patient_id, {})

    coding = condition.get("code", {}).get("coding", [{}])[0]
    status = (
        condition.get("clinicalStatus", {})
        .get("coding", [{}])[0]
        .get("code", "unknown")
    )

    name = _extract_name(patient)
    if not name:
        return None

    return {
        "patient_id": patient_id,
        "name": name,
        "gender": patient.get("gender", "unknown"),
        "birth_date": patient.get("birthDate", "unknown"),
        "condition_code": coding.get("code", ""),
        "condition_display": coding.get("display", ""),
        "condition_status": status,
    }


def _empty_bundle() -> dict:
    return {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}


def _build_bundle(conditions: list[dict], patients: dict[str, dict]) -> dict:
    entries = [{"resource": cond} for cond in conditions]
    entries += [{"resource": patient} for patient in patients.values()]
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries,
    }


def _extract_name(patient: dict) -> str:
    for name_entry in patient.get("name", []):
        family = name_entry.get("family", "")
        given = " ".join(name_entry.get("given", []))
        prefix = " ".join(name_entry.get("prefix", []))
        parts = [p for p in [prefix, given, family] if p]
        if parts:
            return " ".join(parts)
    return ""
