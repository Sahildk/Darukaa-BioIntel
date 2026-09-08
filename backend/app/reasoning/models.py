"""Data models for Phase 7 multi-metric ecological reasoning and evidence gating."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.retrieval.hybrid import ScoredChunk
from app.schemas.evidence import CandidateIntervention
from app.schemas.state import (
    EnvironmentalValueType,
    ProvenanceSource,
    VariableConfidence,
)


class ReasoningVariable(BaseModel):
    """An environmental variable participating in ecological reasoning, with provenance preserved."""
    path: str = Field(..., description="Dotted path e.g. soil.organic_carbon")
    name: str = Field(..., description="Human-readable variable label")
    value: EnvironmentalValueType
    unit: Optional[str] = None
    source: ProvenanceSource = ProvenanceSource.USER
    confidence: VariableConfidence = VariableConfidence.EXPLICIT
    observation_id: Optional[str] = None


class ContextMatchResult(BaseModel):
    """Structured result of evaluating environmental state against context criteria."""
    is_compatible: bool
    matched_conditions: List[str] = Field(default_factory=list)
    unmatched_conditions: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class RelationshipSupportStatus(str, Enum):
    EVIDENCE_SUPPORTED = "evidence_supported"
    UNSUPPORTED_NO_EVIDENCE = "unsupported_no_evidence"
    UNSUPPORTED_INSUFFICIENT_SCOPE = "unsupported_insufficient_scope"
    UNSUPPORTED_CONTEXT_MISMATCH = "unsupported_context_mismatch"
    UNSUPPORTED_INSUFFICIENT_VARIABLES = "unsupported_insufficient_variables"


class RelationshipTemplate(BaseModel):
    """
    Defines matching requirements and required evidence scope for an ecological relationship.
    Does NOT assert universal causal facts; the actual relationship is established ONLY
    when retrieved chunks satisfy all matching, scope, and context requirements.
    """
    template_id: str
    source_variable: str                  # e.g., "soil.organic_carbon"
    target_variable: str                  # e.g., "climate.rainfall" or "biodiversity.habitat_diversity"
    mechanism_pattern: str                # description of the relationship established by evidence
    required_topics: List[str]            # e.g. ["soil_health"]
    required_terms: List[str]             # mechanistic keywords e.g. ["water", "capacity", "retention"]
    directional_indicators: List[str] = Field(
        default_factory=list,
        description="Phrases indicating directional causal influence from source to target",
    )
    applicable_conditions: Dict[str, Any] # context rules evaluated by ContextMatcher
    candidate_intervention_actions: List[str] = Field(default_factory=list)


class EvidenceSupportedRelationship(BaseModel):
    """
    A concrete ecological relationship established and bounded by retrieved scientific evidence.
    Constructed only when retrieved evidence matches a template and satisfies context gates.
    """
    relationship_id: str
    template_id: str
    source_variable: str
    target_variable: str
    mechanism: str
    supporting_chunk_ids: List[str]
    supporting_source_ids: List[str]
    evidence_excerpts: List[str]
    context_match: ContextMatchResult
    support_status: RelationshipSupportStatus
    validation_notes: str


class ReasoningPathway(BaseModel):
    """
    An auditable causal chain connecting >= 3 variables formed by chained sequential evidence-supported relationships.
    Must not contain disconnected or branched leaps.
    """
    pathway_id: str
    title: str
    participating_variables: List[str] = Field(..., min_length=3, description="Must contain >= 3 variables")
    ordered_relationships: List[EvidenceSupportedRelationship]
    evidence_ids: List[str] = Field(default_factory=list, description="Chunk IDs supporting the chain")
    source_ids: List[str] = Field(default_factory=list)
    candidate_interventions: List[CandidateIntervention] = Field(default_factory=list)
    assumptions_and_limitations: List[str] = Field(default_factory=list)
    support_status: RelationshipSupportStatus = RelationshipSupportStatus.EVIDENCE_SUPPORTED


class ScientificSufficiencyResult(BaseModel):
    """
    Evaluates whether the provided environmental state provides a coherent scientific nexus
    capable of supporting multi-metric ecological reasoning.
    """
    is_scientifically_sufficient: bool
    identified_domains: List[str] = Field(default_factory=list)
    matched_templates: List[str] = Field(default_factory=list)
    missing_critical_context: List[str] = Field(default_factory=list)
    evaluation_notes: str


class ReasoningResult(BaseModel):
    """Consolidated output from the Phase 7 ecological reasoning engine."""
    conversation_id: str
    variables_considered: List[ReasoningVariable]
    scientific_sufficiency: ScientificSufficiencyResult
    retrieved_chunks: List[ScoredChunk] = Field(default_factory=list)
    evidence_supported_relationships: List[EvidenceSupportedRelationship] = Field(default_factory=list)
    unsupported_relationships: List[EvidenceSupportedRelationship] = Field(default_factory=list)
    active_pathways: List[ReasoningPathway] = Field(default_factory=list)
    candidate_interventions: List[CandidateIntervention] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    developer_trace: Dict[str, Any] = Field(default_factory=dict)
