from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .catalogue import (
    get_all_packages,
    get_package,
    get_snomed_codes,
    get_snomed_display,
    is_valid_snomed_for_package,
)
from .config import Settings, get_settings
from .fhir import FHIRClient
from .models import (
    ErrorResponse,
    HealthResponse,
    Package,
    PackageDetail,
    PatientMultiQuery,
    PatientMultiQueryResult,
    PatientQueryResult,
    SnomedCode,
)

# ---------------------------------------------------------------------------
# FHIR client lifecycle
# ---------------------------------------------------------------------------

_fhir_client: FHIRClient | None = None


def get_fhir_client() -> FHIRClient:
    if _fhir_client is None:
        raise RuntimeError("FHIR client not initialised")
    return _fhir_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _fhir_client
    settings = get_settings()
    _fhir_client = FHIRClient(
        base_url=settings.fhir_base_url,
        username=settings.fhir_username,
        password=settings.fhir_password,
        cache_ttl=settings.count_cache_ttl,
    )
    yield
    await _fhir_client.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

settings = get_settings()

tags_metadata = [
    {
        "name": "packages",
        "description": (
            "Browse the AB-PMJAY health benefit package catalogue. "
            "Each package groups a set of related SNOMED-coded conditions "
            "for a specific surgical or medical treatment."
        ),
    },
    {
        "name": "patients",
        "description": (
            "Query live patient records from HAPI FHIR. "
            "Filter by package and SNOMED condition code to retrieve matching patient demographics and condition details."
        ),
    },
    {
        "name": "health",
        "description": "Service and FHIR server liveness checks.",
    },
]

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    openapi_tags=tags_metadata,
    license_info={"name": "MIT"},
    contact={"name": "NHA FHIR Platform"},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["health"],
    summary="Service health check",
    description=(
        "Returns the liveness status of this API and whether the configured "
        "HAPI FHIR server is reachable. Safe to call without authentication."
    ),
    response_model=HealthResponse,
)
async def health(
    fhir: FHIRClient = Depends(get_fhir_client),
    cfg: Settings = Depends(get_settings),
):
    reachable = await fhir.ping()
    return HealthResponse(
        status="ok",
        fhir_reachable=reachable,
        fhir_base_url=cfg.fhir_base_url,
    )


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

@app.get(
    "/packages",
    tags=["packages"],
    summary="List all AB-PMJAY packages",
    description=(
        "Returns the AB-PMJAY health benefit packages available in this "
        "catalogue. Each entry includes the package identifier, clinical label, "
        "primary procedure, and the number of SNOMED conditions and patient bundles."
    ),
    response_model=list[Package],
)
async def list_packages():
    return [Package(**p) for p in get_all_packages()]


@app.get(
    "/packages/{package_id}",
    tags=["packages"],
    summary="Get package details with SNOMED codes",
    description=(
        "Returns full details for a single package including all SNOMED-coded "
        "conditions in its catalogue. Each SNOMED entry includes a live patient "
        "count fetched from FHIR (cached for `COUNT_CACHE_TTL` seconds)."
    ),
    response_model=PackageDetail,
    responses={404: {"model": ErrorResponse, "description": "Package not found"}},
)
async def get_package_detail(
    package_id: str,
    fhir: FHIRClient = Depends(get_fhir_client),
):
    pkg = get_package(package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package '{package_id}' not found in catalogue")

    raw_codes = get_snomed_codes(package_id) or []
    snomed_codes = []
    for c in raw_codes:
        count = await fhir.get_condition_count(package_id.upper(), c["code"])
        snomed_codes.append(SnomedCode(code=c["code"], display=c["display"], patient_count=count))

    pkg.pop("snomed_codes", None)
    return PackageDetail(**pkg, snomed_codes=snomed_codes)


@app.get(
    "/packages/{package_id}/snomed-codes",
    tags=["packages"],
    summary="List SNOMED codes for a package",
    description=(
        "Returns all SNOMED-coded conditions in the catalogue for the given package, "
        "each with a live patient count from FHIR. "
        "Counts are cached — see `COUNT_CACHE_TTL` environment variable."
    ),
    response_model=list[SnomedCode],
    responses={404: {"model": ErrorResponse, "description": "Package not found"}},
)
async def list_snomed_codes(
    package_id: str,
    fhir: FHIRClient = Depends(get_fhir_client),
):
    raw_codes = get_snomed_codes(package_id)
    if raw_codes is None:
        raise HTTPException(status_code=404, detail=f"Package '{package_id}' not found in catalogue")

    result = []
    for c in raw_codes:
        count = await fhir.get_condition_count(package_id.upper(), c["code"])
        result.append(SnomedCode(code=c["code"], display=c["display"], patient_count=count))
    return result


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

@app.get(
    "/patients",
    tags=["patients"],
    summary="Query patient records by package and SNOMED condition",
    description=(
        "Retrieves patient records from HAPI FHIR matching the given package "
        "and SNOMED condition code. \n\n"
        "**Two-step FHIR query:** \n"
        "1. Resolve patient IDs from `Coverage.class.value` for the package. \n"
        "2. Fetch `Condition` resources for those patients matching the SNOMED code, "
        "   with `Patient` resources included (`_include=Condition:subject`). \n\n"
        "The requested SNOMED code must belong to the package's catalogue — "
        "cross-package queries are rejected with `422`."
    ),
    response_model=PatientQueryResult,
    responses={
        404: {"model": ErrorResponse, "description": "Package not found"},
        422: {"model": ErrorResponse, "description": "SNOMED code not valid for this package"},
    },
)
async def query_patients(
    package: str = Query(..., description="Package ID (e.g. MG006A)", example="MG006A"),
    snomed_code: str = Query(..., description="SNOMED CT concept code", example="4834000"),
    fhir: FHIRClient = Depends(get_fhir_client),
):
    if not get_package(package):
        raise HTTPException(status_code=404, detail=f"Package '{package}' not found in catalogue")

    if not is_valid_snomed_for_package(package, snomed_code):
        raise HTTPException(
            status_code=422,
            detail=f"SNOMED code '{snomed_code}' is not in the catalogue for package '{package}'",
        )

    display = get_snomed_display(package, snomed_code) or snomed_code
    total, patients, raw = await fhir.get_patients(package.upper(), snomed_code)

    return PatientQueryResult(
        package=package.upper(),
        snomed_code=snomed_code,
        snomed_display=display,
        total=total,
        patients=patients,
        raw=raw,
    )


@app.post(
    "/patients/query",
    tags=["patients"],
    summary="Query patients by package and multiple SNOMED codes",
    description=(
        "Accepts a list of SNOMED codes and retrieves all patient records matching "
        "**any** of them within the given package (OR logic). \n\n"
        "**Single FHIR round-trip:** codes are passed as a comma-separated token "
        "list in one `code` parameter — FHIR treats this as OR natively. \n\n"
        "Codes not found in the package catalogue are returned in `invalid_codes` "
        "and silently excluded from the query rather than rejecting the whole request. "
        "Each patient record includes `condition_code` so you can see which SNOMED "
        "code matched that patient."
    ),
    response_model=PatientMultiQueryResult,
    responses={
        404: {"model": ErrorResponse, "description": "Package not found"},
        422: {"model": ErrorResponse, "description": "No valid SNOMED codes after filtering"},
    },
)
async def query_patients_multi(
    body: PatientMultiQuery,
    fhir: FHIRClient = Depends(get_fhir_client),
):
    if not get_package(body.package):
        raise HTTPException(status_code=404, detail=f"Package '{body.package}' not found in catalogue")

    valid_codes = [c for c in body.snomed_codes if is_valid_snomed_for_package(body.package, c)]
    invalid_codes = [c for c in body.snomed_codes if c not in valid_codes]

    if not valid_codes:
        raise HTTPException(
            status_code=422,
            detail=f"None of the submitted SNOMED codes belong to package '{body.package}'",
        )

    total, patients, raw = await fhir.get_patients_multi(body.package.upper(), valid_codes)

    return PatientMultiQueryResult(
        package=body.package.upper(),
        snomed_codes=valid_codes,
        invalid_codes=invalid_codes,
        total=total,
        patients=patients,
        raw=raw,
    )
