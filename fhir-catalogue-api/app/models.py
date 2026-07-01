from pydantic import BaseModel, Field


class SnomedCode(BaseModel):
    code: str = Field(..., description="SNOMED CT concept identifier", example="4834000")
    display: str = Field(..., description="Human-readable SNOMED concept name", example="Typhoid fever")
    patient_count: int | None = Field(
        None,
        description="Number of patients in FHIR with this condition (null if count fetch failed)",
        example=22,
    )


class Package(BaseModel):
    id: str = Field(..., description="AB-PMJAY Health Benefit Package code", example="MG006A")
    label: str = Field(..., description="Clinical area label", example="Enteric Fever")
    description: str = Field(..., description="Brief description of the package scope")
    procedure: str = Field(..., description="Primary procedure covered", example="Antibiotic therapy")
    procedure_snomed_code: str = Field(..., description="SNOMED CT code for the procedure", example="281789004")
    pre_auth_ref: str = Field(..., description="Pre-authorisation reference used in FHIR claims", example="PA-MG006A")
    snomed_code_count: int = Field(..., description="Number of SNOMED conditions in catalogue for this package")
    bundle_count: int = Field(..., description="Total patient bundles uploaded for this package", example=125)


class PackageDetail(Package):
    snomed_codes: list[SnomedCode] = Field(..., description="All SNOMED conditions catalogued for this package")


class PatientRecord(BaseModel):
    patient_id: str = Field(..., description="FHIR Patient resource ID", example="6721c0cb-10e1-22ad-7729-4fb17edd3461")
    name: str = Field(..., description="Patient full name", example="Mr. Dewey930 Glover433")
    gender: str = Field(..., description="Patient gender", example="male")
    birth_date: str = Field(..., description="Date of birth (YYYY-MM-DD)", example="1947-11-24")
    condition_code: str = Field(..., description="SNOMED code of the diagnosed condition", example="4834000")
    condition_display: str = Field(..., description="Display name of the condition", example="Typhoid fever")
    condition_status: str = Field(..., description="Clinical status of the condition", example="active")


class PatientQueryResult(BaseModel):
    package: str = Field(..., description="Package ID queried", example="MG006A")
    snomed_code: str = Field(..., description="SNOMED code filtered on", example="4834000")
    snomed_display: str = Field(..., description="Display name of the SNOMED code", example="Typhoid fever")
    total: int = Field(..., description="Total number of matching patient records")
    patients: list[PatientRecord]
    raw: dict = Field(
        ...,
        description="Raw, unmodified FHIR Bundle containing every Condition and Patient resource backing this result",
    )


class PatientMultiQuery(BaseModel):
    package: str = Field(..., description="AB-PMJAY package ID to scope the query", example="MG006A")
    snomed_codes: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="One or more SNOMED CT concept codes — all must belong to the given package",
        example=["4834000", "302231008", "7520000"],
    )


class PatientMultiQueryResult(BaseModel):
    package: str = Field(..., description="Package ID queried", example="MG006A")
    snomed_codes: list[str] = Field(..., description="SNOMED codes that were queried")
    invalid_codes: list[str] = Field(
        ...,
        description="Submitted codes rejected because they are not in the package catalogue",
    )
    total: int = Field(..., description="Total number of matching patient records across all codes")
    patients: list[PatientRecord]
    raw: dict = Field(
        ...,
        description="Raw, unmodified FHIR Bundle containing every Condition and Patient resource backing this result",
    )


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    fhir_reachable: bool = Field(..., description="Whether the FHIR server responded to a ping")
    fhir_base_url: str = Field(..., description="Configured FHIR base URL")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message", example="Package 'XY001A' not found in catalogue")
