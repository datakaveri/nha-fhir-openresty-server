# HAPI FHIR Server

## What is FHIR?

**FHIR** (Fast Healthcare Interoperability Resources) is a standard for storing and exchanging healthcare data. Think of it like a universal language that different hospital systems, apps, and devices use to talk to each other. It is maintained by HL7, the body that governs healthcare data standards.

**HAPI FHIR** is an open-source Java implementation of that standard — a ready-made server that stores health data in the FHIR format and exposes a REST API so other systems can read and write that data.

---

## What Does It Do?

HAPI FHIR acts as a **database + API for health records**, where everything is structured around standard "resources":

| Resource | What It Represents |
|---|---|
| `Patient` | A person's demographics (name, date of birth, gender) |
| `Observation` | A measurement (blood pressure, lab result) |
| `Condition` | A diagnosis (diabetes, hypertension) |
| `Medication` | A drug |
| `MedicationRequest` | A prescription |
| `Encounter` | A hospital visit |
| `Practitioner` | A doctor or nurse |
| `Organization` | A hospital or clinic |

You can **Create, Read, Update, and Delete** (CRUD) any of these via standard HTTP calls.

---

## How to Populate Data

There are three main ways to put data into the server:

### 1. Web UI (easiest to start)
Once the server is running at `http://localhost:8080`, it has a built-in UI where you can paste JSON and submit it directly.

### 2. HTTP POST (programmatic)
Send a JSON payload to the server:

```bash
curl -X POST http://localhost:8080/fhir/Patient \
  -H "Content-Type: application/fhir+json" \
  -d '{
    "resourceType": "Patient",
    "name": [{ "family": "Sharma", "given": ["Raj"] }],
    "gender": "male",
    "birthDate": "1985-04-12"
  }'
```

### 3. Bundle Upload (bulk)
Wrap multiple resources in a single `Bundle` JSON and POST them all at once. This is useful for migrating existing data from another system.

---

## Running the Server

```bash
docker compose up -d
```

The FHIR base URL will be available at `http://localhost:8080/fhir` and the web UI at `http://localhost:8080`.

---

## FHIR Versions

| Version | Full Name | Status | Notes |
|---|---|---|---|
| **DSTU2** | Draft Standard for Trial Use 2 | Outdated | Very old, avoid |
| **DSTU3** (STU3) | Draft Standard for Trial Use 3 | Outdated | Still in some legacy systems |
| **R4** | Release 4 | **Current standard** | Most widely adopted globally |
| **R4B** | Release 4B | Minor update to R4 | Fixes a few specific resources |
| **R5** | Release 5 | Latest | Cutting-edge, less tooling/adoption |

This server is configured to use **R4**, which is the right choice for ABDM compliance.

---

## Context: ABDM / NHA

This server is set up for use with the **Ayushman Bharat Digital Mission (ABDM)** under the National Health Authority (NHA), which mandates FHIR R4 compliance. The typical data flow looks like this:

```
Data Source (hospital HIS, app, etc.)
        ↓  transform to FHIR JSON
HAPI FHIR Server  ←→  other systems (PHR apps, HIPs, HIUs)
```
