"""Configuration module for Darukaa BioIntel backend."""
import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings with offline-friendly defaults."""
    app_name: str = "Darukaa BioIntel"
    version: str = "0.1.0"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    api_prefix: str = "/api"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


settings = Settings()
