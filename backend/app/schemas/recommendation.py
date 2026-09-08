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
    """An actionable, evidence-grounded recommendation with full scientific traceability."""
    recommendation_id: Optional[str] = None
    action: str
    rationale: Optional[str] = None
    why: str
    impacted_metrics: List[str]
    time_horizon: TimeHorizon
    evidence_strength: EvidenceStrength
    evidence: List[EvidenceItem] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    source_ids: List[str] = Field(default_factory=list)
    supporting_relationship_ids: List[str] = Field(default_factory=list)
    supporting_pathway_ids: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    claim_validations: List[Any] = Field(default_factory=list)


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
