"""Recommendation generator converting validated candidate interventions into traceable recommendations."""
from typing import Any, Callable, Dict, List, Optional

from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.reasoning.models import ReasoningResult
from app.schemas.recommendation import DeveloperTrace, TimeHorizon
from app.schemas.state import EnvironmentalState
from .evidence import EvidenceResolver
from .models import (
    RecommendationItem,
    RecommendationResult,
    RejectedCandidate,
)
from .validator import EvidenceTraceabilityValidator, ValidationResult


class RecommendationGenerator:
    """
    Coordinates the Phase 8 recommendation pipeline:
    1. Ingests Phase 7 candidate interventions and supported pathways.
    2. Enforces deterministic claim-level evidence, context, contraindication, and quantitative validation.
    3. Resolves full provenance metadata via EvidenceResolver.
    4. Outputs verified RecommendationItem records and rejected candidates with explicit audit logs.
    """

    def __init__(
        self,
        store: Optional[KnowledgeStore] = None,
        validator: Optional[EvidenceTraceabilityValidator] = None,
        resolver: Optional[EvidenceResolver] = None,
        llm_fn: Optional[Callable[[str], str]] = None,
    ):
        if store:
            self.store = store
        else:
            db_path = REPO_ROOT / "data/knowledge.db"
            self.store = KnowledgeStore(db_path=db_path)

        self.resolver = resolver or EvidenceResolver(store=self.store)
        self.validator = validator or EvidenceTraceabilityValidator(store=self.store, resolver=self.resolver)
        self.llm_fn = llm_fn

    def generate(
        self,
        conversation_id: str,
        reasoning_result: ReasoningResult,
        state: EnvironmentalState,
    ) -> RecommendationResult:
        """Generates evidence-grounded recommendations from Phase 7 reasoning output."""
        # 1. Check if scientific sufficiency passed and active pathways exist
        if not reasoning_result.scientific_sufficiency.is_scientifically_sufficient or not reasoning_result.active_pathways:
            return RecommendationResult(
                conversation_id=conversation_id,
                recommendations=[],
                rejected_candidates=[],
                evidence_validation_passed=True,
                limitations=reasoning_result.limitations,
                developer_trace=DeveloperTrace(
                    query=conversation_id,
                    extracted_variables={v.path: v.value for v in reasoning_result.variables_considered},
                    retrieval_query=None,
                    retrieved_source_ids=[],
                    reasoning_variables=[v.path for v in reasoning_result.variables_considered],
                    validation_status="halted_insufficient_scientific_context",
                ),
            )

        recommendations: List[RecommendationItem] = []
        rejected_candidates: List[RejectedCandidate] = []
        all_limitations: List[str] = list(reasoning_result.limitations)

        # Extract pathway IDs and relationship IDs from active pathways
        pathway_ids = [p.pathway_id for p in reasoning_result.active_pathways]
        relationship_ids = sorted(
            list(
                {
                    rel.relationship_id
                    for p in reasoning_result.active_pathways
                    for rel in p.ordered_relationships
                }
            )
        )

        # 2. Iterate through candidate interventions and perform claim-level validation
        for candidate in reasoning_result.candidate_interventions:
            val_result: ValidationResult = self.validator.validate_candidate(candidate, state)

            if val_result.is_valid:
                # Resolve full evidence items
                evidence_items = self.resolver.resolve_evidence_items(val_result.resolved_chunk_ids)

                rec_id = f"REC-{conversation_id[:6]}-{len(recommendations)+1:02d}"

                rec_item = RecommendationItem(
                    recommendation_id=rec_id,
                    action=candidate.action,
                    rationale=candidate.rationale,
                    why=candidate.rationale,
                    impacted_metrics=candidate.affected_metrics,
                    time_horizon=TimeHorizon(candidate.time_horizon),
                    evidence_ids=val_result.resolved_chunk_ids,
                    source_ids=val_result.resolved_source_ids,
                    evidence_strength=val_result.evidence_strength,
                    evidence=evidence_items,
                    supporting_relationship_ids=relationship_ids,
                    supporting_pathway_ids=pathway_ids,
                    contraindications=val_result.active_contraindications,
                    assumptions=[
                        "Intervention impact verified against peer-reviewed literature in matching ecological conditions."
                    ],
                    limitations=val_result.limitations,
                    claim_validations=val_result.claim_records,
                )
                recommendations.append(rec_item)
                all_limitations.extend(val_result.limitations)
            else:
                rejected = RejectedCandidate(
                    candidate_action=candidate.action,
                    reason=val_result.rejection_reason or "Validation failed",
                    rejection_stage=val_result.rejection_stage or "unknown",
                    details="; ".join(val_result.limitations),
                    unsupported_claims=val_result.claim_records,
                )
                rejected_candidates.append(rejected)
                all_limitations.extend(val_result.limitations)

        # 3. Optional LLM narrative synthesis (Allowed ONLY for readable prose, never for claim authorization)
        if self.llm_fn and recommendations:
            try:
                # LLM can synthesize a summary paragraph for developer trace or assessment note
                pass
            except Exception:
                pass

        # 4. Developer Trace
        dev_trace = DeveloperTrace(
            query=conversation_id,
            extracted_variables={v.path: v.value for v in reasoning_result.variables_considered},
            retrieval_query=None,
            retrieved_source_ids=sorted(list({c.source_id for c in reasoning_result.retrieved_chunks})),
            reasoning_variables=[v.path for v in reasoning_result.variables_considered],
            validation_status="passed" if recommendations else "rejected_or_empty",
        )

        return RecommendationResult(
            conversation_id=conversation_id,
            recommendations=recommendations,
            rejected_candidates=rejected_candidates,
            evidence_validation_passed=len(recommendations) > 0,
            limitations=sorted(list(set(all_limitations))),
            developer_trace=dev_trace,
        )
