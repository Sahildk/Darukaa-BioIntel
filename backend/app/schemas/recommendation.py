"""Recommendation and developer observability schemas."""
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from .evidence import EvidenceItem
from .state import EnvironmentalState


class EvidenceStrength(str, Enum):
    STRONG = "Strong"
    MODERATE = "Moderate"
    LIMITED = "Limited"


class TimeHorizon(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class RecommendationItem(BaseModel):
    """An actionable, evidence-grounded recommendation."""
    action: str
    why: str
    impacted_metrics: List[str]
    time_horizon: TimeHorizon
    evidence_strength: EvidenceStrength
    evidence: List[EvidenceItem]


class DeveloperTrace(BaseModel):
    """Developer observability trace for pipeline audit."""
    query: str
    extracted_variables: Dict[str, Any] = Field(default_factory=dict)
    retrieval_query: Optional[str] = None
    retrieved_source_ids: List[str] = Field(default_factory=list)
    reasoning_variables: List[str] = Field(default_factory=list)
    validation_status: str


class RecommendationResponse(BaseModel):
    """Full recommendation payload satisfying API contracts."""
    type: Literal["recommendation"] = "recommendation"
    conversation_id: str
    assessment: str
    variables_considered: List[str]
    recommendations: List[RecommendationItem]
    environmental_state: EnvironmentalState
    limitations: List[str] = Field(default_factory=list)
    developer_trace: Optional[DeveloperTrace] = None
