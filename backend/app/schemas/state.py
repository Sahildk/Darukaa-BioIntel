"""Environmental state schemas with provenance tracking."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field


class ProvenanceSource(str, Enum):
    USER = "user"
    STRUCTURED_INPUT = "structured_input"
    RETRIEVED = "retrieved"
    INFERRED = "inferred"


class VariableConfidence(str, Enum):
    EXPLICIT = "explicit"
    ESTIMATED = "estimated"
    INFERRED = "inferred"


# Constrained primitive type for observed environmental values
EnvironmentalValueType = Union[float, int, str, bool]


class EnvironmentalVariable(BaseModel):
    """Represents an observed or inferred environmental metric with strict provenance."""
    value: EnvironmentalValueType
    unit: Optional[str] = None
    source: ProvenanceSource = ProvenanceSource.USER
    confidence: VariableConfidence = VariableConfidence.EXPLICIT
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    observation_id: Optional[str] = None


class SoilState(BaseModel):
    ph: Optional[EnvironmentalVariable] = None
    organic_carbon: Optional[EnvironmentalVariable] = None
    moisture: Optional[EnvironmentalVariable] = None


class LandUseState(BaseModel):
    land_cover: Optional[EnvironmentalVariable] = None
    crop: Optional[EnvironmentalVariable] = None
    fragmentation: Optional[EnvironmentalVariable] = None


class BiodiversityState(BaseModel):
    species_richness: Optional[EnvironmentalVariable] = None
    habitat_diversity: Optional[EnvironmentalVariable] = None
    pollinator_abundance: Optional[EnvironmentalVariable] = None


class ClimateState(BaseModel):
    temperature: Optional[EnvironmentalVariable] = None
    rainfall: Optional[EnvironmentalVariable] = None


class HumanImpactState(BaseModel):
    pollution: Optional[EnvironmentalVariable] = None
    deforestation: Optional[EnvironmentalVariable] = None


class EnvironmentalState(BaseModel):
    """Comprehensive multi-category environmental state representation."""
    region: Optional[EnvironmentalVariable] = None
    soil: SoilState = Field(default_factory=SoilState)
    land_use: LandUseState = Field(default_factory=LandUseState)
    biodiversity: BiodiversityState = Field(default_factory=BiodiversityState)
    climate: ClimateState = Field(default_factory=ClimateState)
    human_impact: HumanImpactState = Field(default_factory=HumanImpactState)
    active_conflicts: List[Any] = Field(default_factory=list)
    observation_history: List[Any] = Field(default_factory=list)
