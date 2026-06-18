"""
ScrantonOS — Centralized Configuration
=======================================
Pydantic Settings class handling environment mode, API keys, GCP project
descriptors, and global security parameters. Fails gracefully in DEV mode
when cloud credentials are missing.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

# Load .env from the project root
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


class ScrantonConfig(BaseSettings):
    """Global configuration for the ScrantonOS multi-agent system."""

    # ── Environment Mode ─────────────────────────────────────────────
    ENV: Literal["DEV", "PROD"] = "DEV"

    # ── Gemini / ADK ─────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""

    # ── GCP (required only in PROD) ──────────────────────────────────
    GCP_PROJECT_ID: str = ""
    GCP_REGION: str = "us-central1"

    # ── Security ─────────────────────────────────────────────────────
    # HMAC secret used to sign HITL approval tokens.
    # In DEV mode a default placeholder is acceptable.
    IAM_APPROVAL_SECRET: str = "dev-secret-not-for-production"

    # ── Limits ───────────────────────────────────────────────────────
    # Maximum cumulative token spend per single workflow execution loop.
    MAX_TOKEN_BUDGET: int = 50_000

    # ── Server ───────────────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ── Sub-Agents Custom Configurations ─────────────────────────────
    GITHUB_REPO: str = ""
    GITHUB_TOKEN: str = ""
    LOCAL_REPO_PATH: str = ""
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_PATH: str = ""
    GCP_LOG_FILTER: str = ""
    GCP_BILLING_DATASET: str = ""


    # ── IAM Whitelist ────────────────────────────────────────────────
    # Hardcoded safe roles that Stanley will allow without escalation.
    IAM_ROLE_WHITELIST: list[str] = [
        "roles/viewer",
        "roles/browser",
        "roles/storage.objectViewer",
        "roles/logging.viewer",
        "roles/monitoring.viewer",
        "roles/bigquery.dataViewer",
        "roles/bigquery.jobUser",
        "roles/cloudsql.viewer",
        "roles/iam.securityReviewer",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    # ── Validators ───────────────────────────────────────────────────

    @field_validator("ENV", mode="before")
    @classmethod
    def normalize_env(cls, v: str) -> str:
        return v.upper().strip()

    @model_validator(mode="after")
    def check_prod_requirements(self) -> "ScrantonConfig":
        """Ensure critical credentials exist in PROD mode."""
        if self.ENV == "PROD":
            if not self.GCP_PROJECT_ID:
                raise ValueError("PROD mode requires GCP_PROJECT_ID to be set.")
            
            # If GEMINI_API_KEY is not in env, attempt to fetch from GCP Secret Manager
            if not self.GEMINI_API_KEY:
                print(f"Fetching GEMINI_API_KEY from Secret Manager in project {self.GCP_PROJECT_ID}...")
                try:
                    from google.cloud import secretmanager
                    client = secretmanager.SecretManagerServiceClient()
                    name = f"projects/{self.GCP_PROJECT_ID}/secrets/GEMINI_API_KEY/versions/latest"
                    response = client.access_secret_version(request={"name": name})
                    self.GEMINI_API_KEY = response.payload.data.decode("UTF-8")
                except Exception as e:
                    raise ValueError(f"Failed to fetch GEMINI_API_KEY from Secret Manager: {e}")

            # Also attempt to fetch IAM_APPROVAL_SECRET if it's the default dev one
            if self.IAM_APPROVAL_SECRET == "dev-secret-not-for-production":
                print(f"Fetching IAM_APPROVAL_SECRET from Secret Manager...")
                try:
                    from google.cloud import secretmanager
                    client = secretmanager.SecretManagerServiceClient()
                    name = f"projects/{self.GCP_PROJECT_ID}/secrets/IAM_APPROVAL_SECRET/versions/latest"
                    response = client.access_secret_version(request={"name": name})
                    self.IAM_APPROVAL_SECRET = response.payload.data.decode("UTF-8")
                except Exception as e:
                    print(f"Warning: Failed to fetch IAM_APPROVAL_SECRET from Secret Manager: {e}")

        return self

    @property
    def is_dev(self) -> bool:
        return self.ENV == "DEV"

    @property
    def is_prod(self) -> bool:
        return self.ENV == "PROD"


@lru_cache(maxsize=1)
def get_config() -> ScrantonConfig:
    """Singleton accessor for the global configuration."""
    return ScrantonConfig()
