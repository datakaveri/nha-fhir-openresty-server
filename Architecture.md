┌─────────────────────────────────────────────────────┐
│ Browser (UI) │
│ │
│ [Package Cards] → [SNOMED Selector] → [Table] │
└────────────────────────┬────────────────────────────┘
│ REST
┌────────────────────────▼────────────────────────────┐
│ Catalogue API (FastAPI) │
│ │
│ GET /packages │
│ GET /packages/{id}/snomed-codes │
│ GET /patients?package={id}&snomed={code} │
│ │
│ ┌──────────────────┐ ┌──────────────────────┐ │
│ │ Static Catalogue │ │ FHIR Query Layer │ │
│ │ (from STG files) │ │ (HAPI FHIR client) │ │
│ └──────────────────┘ └──────────────────────┘ │
└─────────────────────────────┬───────────────────────┘
│ FHIR R4
┌─────────────────────────────▼───────────────────────┐
│ HAPI FHIR (localhost:8080/fhir) │
│ behind OpenResty (Basic auth) │
└─────────────────────────────────────────────────────┘

Component 1 — Static Catalogue (build once at startup)
Read the STG files and emit a map like:

CATALOGUE = {
"MG006A": {
"label": "Enteric Fever",
"stg_file": "PS1_STG2.json",
"snomed_codes": [
{"code": "4834000", "display": "Typhoid fever"},
{"code": "302231008", "display": "Salmonella infection"},
...
]
},
"SG039C": { ... },
...
}

Source: snomed_mapped/NHA/PS1/PS1_STG{N}.json → mappings[] filtered to clinically meaningful entities (same curated list used during variance generation).

Component 2 — API Endpoints
Method Path Returns
GET /packages 4 package cards (id, label, snomed count, bundle count)
GET /packages/{id}/snomed-codes List of {code, display} from STG catalogue
GET /patients?package={id}&snomed={code} Patient rows from FHIR

Component 3 — FHIR Query Strategy
The key join: Coverage.class.value = "{packageCode}" links a patient to a package.

Two-step query (reliable on HAPI):

Step 1 — get Patient IDs for the package:
GET /fhir/Coverage?class-value=MG006A&\_elements=subscriber&\_count=200

Step 2 — get Conditions matching the SNOMED code for those patients:
GET /fhir/Condition
?code=http://snomed.info/sct|4834000
&subject=Patient/id1,Patient/id2,...
&\_include=Condition:subject
Result: a FHIR Bundle containing Condition + Patient resources — everything needed for the table.

Single-step alternative (if HAPI \_has is enabled):

GET /fhir/Condition
?code=http://snomed.info/sct|{snomedCode}
&subject:Patient.\_has:Coverage:subscriber:class-value={packageCode}
&\_include=Condition:subject

Component 4 — UI Flow

Landing page
└── 4 cards: MG006A | MG064A | SB039A | SG039C
each showing: label, procedure, bundle count

Package page (e.g. MG006A — Enteric Fever)
└── SNOMED code dropdown / chip selector
(populated from catalogue API)
└── [Fetch Patients] button

Results page
└── Table: Patient ID | Name | Age | Gender | Condition | Date
└── Download as CSV / JSON
