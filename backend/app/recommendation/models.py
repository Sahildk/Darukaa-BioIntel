"""Phase 8 recommendation and claim-level validation data models."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.evidence import EvidenceItem
from app.schemas.recommendation import DeveloperTrace, EvidenceStrength, RecommendationItem, TimeHorizon


class ClaimValidationStatus(str, Enum):
    """Validation status for an individual scientific claim."""
    SUPPORTED = "supported"
    UNSUPPORTED_NO_EVIDENCE = "unsupported_no_evidence"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    CONTEXT_MISMATCH = "context_mismatch"
    QUANTITATIVE_CLAIM_UNSUPPORTED = "quantitative_claim_unsupported"
    CONTRAINDICATION_BLOCKED = "contraindication_blocked"


class ClaimValidationRecord(BaseModel):
    """Audit record for a discrete scientific claim within a candidate recommendation."""
    claim_id: str
    claim_type: str = Field(..., description="'intervention_applicability' | 'mechanism_support' | 'context_compatibility' | 'quantitative_claim' | 'contraindication'")
    claim_text: str
    status: ClaimValidationStatus
    supporting_chunk_ids: List[str] = Field(default_factory=list)
    details: str


class RejectedCandidate(BaseModel):
    """Diagnostic record for a candidate intervention rejected during validation."""
    candidate_action: str
    reason: str
    rejection_stage: str = Field(..., description="'evidence' | 'mechanism' | 'context' | 'contraindication' | 'quantitative'")
    details: str
    unsupported_claims: List[ClaimValidationRecord] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    """Consolidated Phase 8 recommendation outcome."""
    conversation_id: str
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    rejected_candidates: List[RejectedCandidate] = Field(default_factory=list)
    evidence_validation_passed: bool
    limitations: List[str] = Field(default_factory=list)
    developer_trace: Optional[DeveloperTrace] = None
