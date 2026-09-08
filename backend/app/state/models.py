"""State models for observation history, authority levels, and conflict tracking."""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field

from app.schemas.state import (
    EnvironmentalValueType,
    EnvironmentalVariable,
    ProvenanceSource,
    VariableConfidence,
)


class AuthorityLevel(int, Enum):
    """Authority rank determining deterministic overwrite precedence."""
    INFERRED = 1
    EXTERNAL = 2
    USER_DIRECT = 3


def get_authority_level(source: ProvenanceSource) -> AuthorityLevel:
    """
    Separates provenance (data origin) from authority tier:
    - User direct statements and structured JSON payloads share highest authority (USER_DIRECT).
    - Retrieved external database records are mid-tier (EXTERNAL).
    - Inferred/derived values are lowest-tier (INFERRED).
    """
    if source in (ProvenanceSource.USER, ProvenanceSource.STRUCTURED_INPUT):
        return AuthorityLevel.USER_DIRECT
    if source == ProvenanceSource.RETRIEVED:
        return AuthorityLevel.EXTERNAL
    return AuthorityLevel.INFERRED


class EnvironmentalObservation(BaseModel):
    """An immutable, individual observation record with a stable unique ID."""
    observation_id: str = Field(..., description="Stable unique identifier e.g. OBS-soil.ph-001")
    variable_path: str = Field(..., description="Dotted path e.g. soil.organic_carbon")
    value: EnvironmentalValueType
    unit: Optional[str] = None
    source: ProvenanceSource = ProvenanceSource.USER
    confidence: VariableConfidence = VariableConfidence.EXPLICIT
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_variable(self) -> EnvironmentalVariable:
        """Converts observation into active EnvironmentalVariable."""
        return EnvironmentalVariable(
            value=self.value,
            unit=self.unit,
            source=self.source,
            confidence=self.confidence,
            timestamp=self.timestamp,
            observation_id=self.observation_id,
        )


class ConflictRecord(BaseModel):
    """Represents an explicit, unresolved or resolved contradiction between observations."""
    conflict_id: str
    variable_path: str
    existing_observation_id: str
    incoming_observation_id: str
    status: Literal["unresolved", "resolved"] = "unresolved"
    resolved_observation_id: Optional[str] = None
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    explanation: str


class UpdateResult(BaseModel):
    """Result of an update operation on the environmental state."""
    variable_path: str
    observation_id: str
    status: Literal["applied", "rejected_precedence", "conflict_detected"]
    message: str
    conflict: Optional[ConflictRecord] = None
