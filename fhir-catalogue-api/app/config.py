from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # FHIR server — in Docker this points directly to the HAPI container
    fhir_base_url: str = "http://fhir:8080/fhir"
    fhir_username: str = ""
    fhir_password: str = ""

    # How long (seconds) to cache patient-ID lists and SNOMED counts from FHIR
    count_cache_ttl: int = 300

    # Path where snomed_mapped/NHA/PS1/ STG files are mounted
    snomed_mapped_dir: str = "/app/snomed_mapped"

    # App metadata shown in Swagger
    app_title: str = "FHIR Package Catalogue API"
    app_description: str = (
        "Catalogue API for NHA AB-PMJAY health benefit packages. "
        "Browse packages, explore SNOMED-coded conditions, and retrieve patient data from HAPI FHIR."
    )
    app_version: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
