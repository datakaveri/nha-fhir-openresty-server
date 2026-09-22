# FHIR Bundle Data — Sensitivity & Composition Notes

Covers the two local archives pulled/generated from PMJAY-linked sources:
- `fhir_legacy_bundles/` — raw searchset pages pulled from `https://aaehackathon.nhaad.in/fhir` (10 resource types, 2,585 resources)
- `fhir_v6/` — 676 per-case transaction bundles (BOCW / AROGYAK schemes)

## fhir_legacy_bundles/

### Sensitive data types

| Category | Field(s) | Example |
|---|---|---|
| Full name | `Patient.name`, `Practitioner.name` | `"Janak Devi Sevadarani"`, `"Dr sanjay kumar"` |
| Government/scheme beneficiary IDs | `Patient.identifier`, `Coverage.identifier`, `Claim.identifier` | PMJAY `patientnumber`, `beneficiary-id` (e.g. `PI517RD38`) |
| Date of birth | `Patient.birthDate` (23 occurrences) | `1948-01-01` |
| Gender | `Patient.gender` | `male` / `female` |
| Deceased status/date | `Patient.deceasedDateTime` (9), `deceasedBoolean` (1) | `2024-04-01T00:00:00` |
| Address | `Patient.address` (63 occurrences) | state code (partial in samples seen) |
| Phone numbers | `Practitioner.telecom`, `Organization.telecom` (96 occurrences) | `9540726536` |
| Clinical diagnoses | `Condition.code`, `Claim.diagnosis` | ICD-11 + SNOMED, e.g. "Myasthenia gravis" |
| Procedures performed | `Procedure.code`, `performedDateTime`, `performer` | "Hemiarthroplasty" |
| Financial/claim data | `Claim.item`, `ClaimResponse.item.adjudication` | line-item amounts (INR), approval status |
| Provider/hospital identity | `Organization.name` (address baked into name string) | `"THE MEDICITY RUDRAPUR..."` |
| Doctor registration number | `Practitioner.identifier` | `doctor-registration` value |
| Cross-linkage identifiers | `identifier` (many namespaces resolving to same patient) | case number, beneficiary ID, provider ID |

Note: `DocumentReference` attachments in this archive are already pre-masked upstream (`MASKED_ATTACHMENT_URL` / `MASKED_DOCUMENT_TITLE`); the 240 entries without the `MASKED` marker are all `status: Missing` placeholders with no real attachment content.

### Resource type counts

| Resource Type | Count | Pages |
|---|---:|---:|
| Claim | 63 | 1 |
| ClaimResponse | 10 | 1 |
| Condition | 74 | 1 |
| Coverage | 63 | 1 |
| DocumentReference | 2,154 | 22 |
| Encounter | 10 | 1 |
| Organization | 55 | 1 |
| Patient | 63 | 1 |
| Practitioner | 27 | 1 |
| Procedure | 66 | 1 |
| **Total** | **2,585** | 31 |

### SNOMED CT codes

| Resource Type | SNOMED occurrences |
|---|---:|
| Claim | 587 |
| DocumentReference | 205 |
| Procedure | 99 |
| Condition | 93 |
| Encounter | 41 |
| **Total occurrences** | **1,025** |
| **Unique SNOMED codes** | **133** |

---

## fhir_v6/

### Sensitive data types

| Category | Field(s) | Example |
|---|---|---|
| Full name | `Patient.name` | `"Anto blesson"`, `"Suraji devi"` |
| Case/claim identifiers | `Claim.identifier` | `"BOCW/BR/2025/R3/1021588558"` |
| Clinical diagnoses | `Condition.code` | ICD/SNOMED text |
| Lab/vitals results | `Observation` (22,178 resources) | actual values, units, reference ranges, interpretation flags — e.g. bilirubin `0.05 mg/dL` |
| Medications prescribed | `MedicationStatement` (12,129 resources) | drug name, dose, duration — e.g. `"Aciloc tab 150mg 1x2 Time (3 Days)"` |
| Diagnostic reports / discharge summaries | `DiagnosticReport`, `Composition` | titled documents linking full observation sets to one patient |
| Allergies | `AllergyIntolerance` (150 resources) | coded allergy/intolerance data |
| Family history | `FamilyMemberHistory` (33 resources) | relative's condition history |
| Immunizations | `Immunization` (6 resources) | vaccination records |
| **Unmasked attachment URLs leaking PII** | `DocumentReference.content.attachment.url` (15,410 resources, **not masked**) | `.../ANTO%20BLE9567_20260415_0001.pdf` — embeds patient name fragment + provider ID + claim/case number, pointing at a real internal storage path |
| Provider identity | `Organization.name` (2,724 resources) | lab/hospital names, e.g. `"Life Patho Lab"` |
| Invoices | `Invoice` (753 resources) | billing records tied to patient |
| Consent records | `Consent` (196 resources) | linked to patient via `sourceReference` |
| Phone numbers | `telecom` (1 occurrence) | rare in this archive vs. legacy bundles |

Note: unlike `fhir_legacy_bundles/`, this archive does **not** mask `DocumentReference` attachment URLs — this is the single riskiest field, since the filename itself frequently contains a fragment of the patient's name alongside the provider/claim IDs.

### Resource type counts

| Resource Type | Count |
|---|---:|
| Observation | 22,178 |
| DocumentReference | 15,410 |
| MedicationStatement | 12,129 |
| Condition | 5,486 |
| DiagnosticReport | 2,833 |
| Organization | 2,724 |
| Procedure | 1,944 |
| Composition | 1,762 |
| Invoice | 753 |
| Claim | 692 |
| Patient | 676 |
| Device | 554 |
| Coverage | 276 |
| Specimen | 247 |
| Consent | 196 |
| AllergyIntolerance | 150 |
| FamilyMemberHistory | 33 |
| Encounter | 7 |
| Immunization | 6 |
| **Total** | **68,056** |
| **Case bundles (files)** | **676** |

### SNOMED CT codes

| Resource Type | SNOMED occurrences |
|---|---:|
| Observation | 10,619 |
| Condition | 5,119 |
| MedicationStatement | 5,568 |
| Procedure | 1,845 |
| AllergyIntolerance | 46 |
| Specimen | 19 |
| **Total occurrences** | **23,216** |
| **Unique SNOMED codes** | **1,949** |
