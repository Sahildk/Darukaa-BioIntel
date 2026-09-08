"""Phase 7 Multi-Metric Ecological Reasoning package."""
from .context import ContextMatcher
from .engine import EcologicalReasoningEngine
from .models import (
    ContextMatchResult,
    EvidenceSupportedRelationship,
    ReasoningPathway,
    ReasoningResult,
    ReasoningVariable,
    RelationshipSupportStatus,
    RelationshipTemplate,
    ScientificSufficiencyResult,
)
from .sufficiency import ScientificSufficiencyEvaluator
from .templates import INTERVENTION_SPECS, RELATIONSHIP_TEMPLATES

__all__ = [
    "EcologicalReasoningEngine",
    "ReasoningVariable",
    "ContextMatchResult",
    "RelationshipSupportStatus",
    "RelationshipTemplate",
    "EvidenceSupportedRelationship",
    "ReasoningPathway",
    "ScientificSufficiencyResult",
    "ReasoningResult",
    "ContextMatcher",
    "ScientificSufficiencyEvaluator",
    "RELATIONSHIP_TEMPLATES",
    "INTERVENTION_SPECS",
]
