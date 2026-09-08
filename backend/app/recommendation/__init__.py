"""Phase 8 recommendation generation and evidence traceability validation package."""
from .evidence import EvidenceResolver
from .generator import RecommendationGenerator
from .models import (
    ClaimValidationRecord,
    ClaimValidationStatus,
    RecommendationItem,
    RecommendationResult,
    RejectedCandidate,
)
from .validator import EvidenceTraceabilityValidator, ValidationResult

__all__ = [
    "ClaimValidationRecord",
    "ClaimValidationStatus",
    "RecommendationItem",
    "RejectedCandidate",
    "RecommendationResult",
    "EvidenceResolver",
    "EvidenceTraceabilityValidator",
    "ValidationResult",
    "RecommendationGenerator",
]
