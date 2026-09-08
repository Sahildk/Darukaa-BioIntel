"""Ecological reasoning engine generating evidence-constrained multi-metric pathways."""
from typing import Any, Callable, Dict, List, Optional, Set
from pydantic import BaseModel

from app.knowledge.indexer import InvertedIndex
from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.retrieval.hybrid import HybridRetriever, ScoredChunk
from app.schemas.evidence import CandidateIntervention
from app.schemas.state import EnvironmentalState, EnvironmentalVariable
from app.state.manager import _get_nested_attr, VALID_VARIABLE_PATHS
from .context import ContextMatcher
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


VARIABLE_LABELS: Dict[str, str] = {
    "region": "Regional Climate Zone",
    "soil.organic_carbon": "Soil Organic Carbon",
    "soil.ph": "Soil pH",
    "soil.moisture": "Soil Moisture",
    "land_use.land_cover": "Land Cover / Management Practice",
    "land_use.crop": "Crop Type",
    "land_use.fragmentation": "Habitat Fragmentation",
    "biodiversity.species_richness": "Species Richness",
    "biodiversity.habitat_diversity": "Habitat Diversity",
    "biodiversity.pollinator_abundance": "Pollinator Abundance",
    "climate.temperature": "Temperature",
    "climate.rainfall": "Rainfall / Water Regime",
    "human_impact.pollution": "Chemical Pollution",
    "human_impact.deforestation": "Deforestation Pressure",
}


class EcologicalReasoningEngine:
    """
    Core Phase 7 reasoning engine.
    Constrained by retrieved scientific evidence and deterministic context gates:
    - Strictly enforces: No Evidence -> No Relationship (T-009).
    - Assembles genuinely sequential multi-variable pathways without fabricating leaps.
    - Operates 100% deterministically offline; pluggable LLM is only used for optional narrative framing.
    """

    def __init__(
        self,
        store: Optional[KnowledgeStore] = None,
        index: Optional[InvertedIndex] = None,
        retriever: Optional[HybridRetriever] = None,
        context_matcher: Optional[ContextMatcher] = None,
        sufficiency_evaluator: Optional[ScientificSufficiencyEvaluator] = None,
        templates: Optional[List[RelationshipTemplate]] = None,
        llm_fn: Optional[Callable[[str], str]] = None,
    ):
        if retriever:
            self.retriever = retriever
            self.store = store or retriever.store
            self.index = index or retriever.index
        else:
            db_path = REPO_ROOT / "data/knowledge.db"
            index_path = REPO_ROOT / "data/lexical_index.json"
            self.store = store or KnowledgeStore(db_path=db_path)
            self.index = index or InvertedIndex.load_from_file(index_path)
            self.retriever = HybridRetriever(self.store, self.index)

        self.context_matcher = context_matcher or ContextMatcher()
        self.sufficiency_evaluator = sufficiency_evaluator or ScientificSufficiencyEvaluator()
        self.templates = templates or RELATIONSHIP_TEMPLATES
        self.llm_fn = llm_fn

    def reason(self, conversation_id: str, state: EnvironmentalState) -> ReasoningResult:
        """
        Executes multi-metric ecological reasoning over current state.
        Never fabricates unevidenced relationships.
        """
        # Step 1: Extract ReasoningVariables from state
        variables_considered = self._extract_reasoning_variables(state)

        # Step 2: Scientific Sufficiency Check
        sufficiency = self.sufficiency_evaluator.evaluate(state)
        if not sufficiency.is_scientifically_sufficient:
            return ReasoningResult(
                conversation_id=conversation_id,
                variables_considered=variables_considered,
                scientific_sufficiency=sufficiency,
                retrieved_chunks=[],
                evidence_supported_relationships=[],
                unsupported_relationships=[],
                active_pathways=[],
                candidate_interventions=[],
                limitations=sufficiency.missing_critical_context,
                developer_trace={
                    "status": "insufficient_scientific_context",
                    "missing": sufficiency.missing_critical_context,
                },
            )

        # Step 3: Multi-query hybrid retrieval using existing Phase 4 HybridRetriever
        retrieved_chunks = self._perform_multi_query_retrieval(state, sufficiency.identified_domains)

        # Step 4: Evaluate Candidate Relationship Templates
        supported_rels: List[EvidenceSupportedRelationship] = []
        unsupported_rels: List[EvidenceSupportedRelationship] = []

        populated_paths = {v.path for v in variables_considered}

        for tpl in self.templates:
            # 4a. Check if participating variables exist in state or represent active outcomes
            if tpl.source_variable not in populated_paths:
                continue

            # 4b. Context Compatibility Gate
            ctx_match: ContextMatchResult = self.context_matcher.match(state, tpl.applicable_conditions)
            if not ctx_match.is_compatible:
                unsupported_rels.append(
                    EvidenceSupportedRelationship(
                        relationship_id=f"REL-{tpl.template_id}-UNSUPPORTED",
                        template_id=tpl.template_id,
                        source_variable=tpl.source_variable,
                        target_variable=tpl.target_variable,
                        mechanism=tpl.mechanism_pattern,
                        supporting_chunk_ids=[],
                        supporting_source_ids=[],
                        evidence_excerpts=[],
                        context_match=ctx_match,
                        support_status=RelationshipSupportStatus.UNSUPPORTED_CONTEXT_MISMATCH,
                        validation_notes=f"Context criteria violated: {', '.join(ctx_match.reasons)}",
                    )
                )
                continue

            # 4c. Evidence Scope Gate (Evidence-supported vs merely evidence-present)
            matching_chunks = self._find_substantiating_chunks(tpl, retrieved_chunks)

            if not matching_chunks:
                unsupported_rels.append(
                    EvidenceSupportedRelationship(
                        relationship_id=f"REL-{tpl.template_id}-NO-EVID",
                        template_id=tpl.template_id,
                        source_variable=tpl.source_variable,
                        target_variable=tpl.target_variable,
                        mechanism=tpl.mechanism_pattern,
                        supporting_chunk_ids=[],
                        supporting_source_ids=[],
                        evidence_excerpts=[],
                        context_match=ctx_match,
                        support_status=RelationshipSupportStatus.UNSUPPORTED_NO_EVIDENCE,
                        validation_notes="No retrieved chunk in active pool substantiates this specific directional mechanism.",
                    )
                )
                continue

            # Evidence verified and context satisfied
            chunk_ids = [c.chunk_id for c in matching_chunks]
            source_ids = sorted(list({c.source_id for c in matching_chunks}))
            excerpts = [c.text[:250].strip() + "..." for c in matching_chunks[:2]]

            rel = EvidenceSupportedRelationship(
                relationship_id=f"REL-{tpl.template_id}-ACTIVE",
                template_id=tpl.template_id,
                source_variable=tpl.source_variable,
                target_variable=tpl.target_variable,
                mechanism=tpl.mechanism_pattern,
                supporting_chunk_ids=chunk_ids,
                supporting_source_ids=source_ids,
                evidence_excerpts=excerpts,
                context_match=ctx_match,
                support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
                validation_notes=f"Substantiated by {len(chunk_ids)} chunk(s) across sources: {', '.join(source_ids)}.",
            )
            supported_rels.append(rel)

        # Step 5: Assemble Genuinely Sequential Multi-Variable Pathways
        # Constraint: Do not construct A -> B -> C from independent evidence for A -> B and A -> C
        active_pathways = self._assemble_sequential_pathways(supported_rels, state)

        # Step 6: Generate Candidate Interventions
        candidate_interventions = self._generate_candidate_interventions(active_pathways, state)

        # Step 7: Compile Limitations
        limitations: List[str] = []
        if not active_pathways:
            limitations.append(
                "Retrieved corpus evidence could not substantiate a complete multi-variable causal pathway for the current state."
            )
        for un_rel in unsupported_rels:
            if un_rel.support_status == RelationshipSupportStatus.UNSUPPORTED_CONTEXT_MISMATCH:
                limitations.append(
                    f"Relationship '{un_rel.source_variable} -> {un_rel.target_variable}' omitted due to local context mismatch: {un_rel.validation_notes}"
                )

        trace = {
            "conversation_id": conversation_id,
            "variables_count": len(variables_considered),
            "retrieved_chunks_count": len(retrieved_chunks),
            "supported_relationships_count": len(supported_rels),
            "unsupported_relationships_count": len(unsupported_rels),
            "active_pathways_count": len(active_pathways),
            "candidate_interventions_count": len(candidate_interventions),
        }

        return ReasoningResult(
            conversation_id=conversation_id,
            variables_considered=variables_considered,
            scientific_sufficiency=sufficiency,
            retrieved_chunks=retrieved_chunks,
            evidence_supported_relationships=supported_rels,
            unsupported_relationships=unsupported_rels,
            active_pathways=active_pathways,
            candidate_interventions=candidate_interventions,
            limitations=limitations,
            developer_trace=trace,
        )

    def _extract_reasoning_variables(self, state: EnvironmentalState) -> List[ReasoningVariable]:
        """Extracts populated variables preserving complete provenance."""
        vars_list: List[ReasoningVariable] = []
        for path in sorted(list(VALID_VARIABLE_PATHS)):
            var: Optional[EnvironmentalVariable] = _get_nested_attr(state, path)
            if var is not None and var.value is not None and str(var.value).strip() != "":
                vars_list.append(
                    ReasoningVariable(
                        path=path,
                        name=VARIABLE_LABELS.get(path, path),
                        value=var.value,
                        unit=var.unit,
                        source=var.source,
                        confidence=var.confidence,
                        observation_id=var.observation_id,
                    )
                )
        return vars_list

    def _perform_multi_query_retrieval(
        self,
        state: EnvironmentalState,
        domains: List[str],
    ) -> List[ScoredChunk]:
        """Performs multi-query hybrid retrieval targeted to state variables and domains."""
        queries: List[str] = []

        # Domain-targeted search queries
        if "soil_climate_management" in domains:
            queries.append("soil organic carbon drylands rainfall legume cover crops conservation tillage")
            queries.append("monoculture soil degradation carbon pool water use efficiency Lal FAO")
        if "biodiversity_habitat_management" in domains:
            queries.append("agricultural diversification wild pollinator density hedgerows flowering borders")
            queries.append("polyculture biodiversity ecosystem stability crop yield Tamburini Garibaldi")
        if "landscape_connectivity" in domains:
            queries.append("habitat fragmentation ecological corridors landscape connectivity IPBES")
        if not queries:
            queries.append("soil health biodiversity conservation agriculture agroforestry drylands")

        all_scored: Dict[str, ScoredChunk] = {}
        for q in queries:
            results = self.retriever.retrieve(query=q, top_k=5, mode="hybrid")
            for chunk in results:
                if chunk.chunk_id not in all_scored or chunk.score > all_scored[chunk.chunk_id].score:
                    all_scored[chunk.chunk_id] = chunk

        # Return sorted by score descending
        return sorted(list(all_scored.values()), key=lambda c: c.score, reverse=True)

    def _find_substantiating_chunks(
        self,
        tpl: RelationshipTemplate,
        retrieved_chunks: List[ScoredChunk],
    ) -> List[ScoredChunk]:
        """
        Gating filter: requires both topic/term overlap AND specific directional mechanism presence.
        A chunk is NOT accepted simply because it appeared in the top-k results.
        """
        matching: List[ScoredChunk] = []

        req_topics = set(tpl.required_topics)
        req_terms = [t.lower() for t in tpl.required_terms]
        dir_terms = [d.lower() for d in tpl.directional_indicators]

        for chunk in retrieved_chunks:
            # 1. Topic overlap
            if chunk.topic not in req_topics:
                continue

            text_lower = chunk.text.lower()

            # 2. Mechanistic required terms check
            has_required_terms = all(term in text_lower for term in req_terms)
            if not has_required_terms:
                continue

            # 3. Directional mechanism check: must contain language asserting causal/functional impact
            if dir_terms:
                has_directional = any(d in text_lower for d in dir_terms)
                if not has_directional:
                    continue

            matching.append(chunk)

        return matching

    def _assemble_sequential_pathways(
        self,
        supported_rels: List[EvidenceSupportedRelationship],
        state: EnvironmentalState,
    ) -> List[ReasoningPathway]:
        """
        Assembles multi-variable pathways containing >= 3 distinct variables.
        Strict rule: Edges must be sequential (target of R1 == source of R2).
        Do NOT construct A -> B -> C from A -> B and A -> C.
        """
        pathways: List[ReasoningPathway] = []
        rel_map: Dict[str, List[EvidenceSupportedRelationship]] = {}
        for r in supported_rels:
            rel_map.setdefault(r.source_variable, []).append(r)

        # Search for 2-step sequences R1 (A -> B) and R2 (B -> C) where A, B, C are distinct
        for r1 in supported_rels:
            a = r1.source_variable
            b = r1.target_variable

            # Look for r2 starting from b
            candidates_r2 = rel_map.get(b, [])
            for r2 in candidates_r2:
                c = r2.target_variable
                if c != a and c != b:
                    # Valid sequential chain: A -> B -> C
                    all_evidence_ids = sorted(list(set(r1.supporting_chunk_ids + r2.supporting_chunk_ids)))
                    all_source_ids = sorted(list(set(r1.supporting_source_ids + r2.supporting_source_ids)))

                    pathways.append(
                        ReasoningPathway(
                            pathway_id=f"PATH-{a.replace('.', '_')}-TO-{c.replace('.', '_')}",
                            title=f"Ecological Cascade: {VARIABLE_LABELS.get(a, a)} -> {VARIABLE_LABELS.get(b, b)} -> {VARIABLE_LABELS.get(c, c)}",
                            participating_variables=[a, b, c],
                            ordered_relationships=[r1, r2],
                            evidence_ids=all_evidence_ids,
                            source_ids=all_source_ids,
                            candidate_interventions=[],
                            assumptions_and_limitations=[
                                "Sequential relationships established from verified empirical literature in consistent ecological context."
                            ],
                            support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
                        )
                    )

        # If no strict 2-step sequence formed, check for established ecological cascade:
        # e.g., Land cover (monoculture) affects both SOC and Pollinators in the same agricultural parcel,
        # but only when SOC is linked to water retention, forming:
        # Land Cover -> SOC -> Water Retention
        # The sequential check above covers this!

        return pathways

    def _generate_candidate_interventions(
        self,
        pathways: List[ReasoningPathway],
        state: EnvironmentalState,
    ) -> List[CandidateIntervention]:
        """
        Generates structured candidate interventions from evidence-supported pathways.
        Includes contraindications and verified evidence IDs without fabricated numbers.
        """
        interventions: List[CandidateIntervention] = []
        seen_actions: Set[str] = set()

        for pathway in pathways:
            for rel in pathway.ordered_relationships:
                # Find template matching this relationship
                tpl = next((t for t in self.templates if t.template_id == rel.template_id), None)
                if not tpl:
                    continue

                for action_name in tpl.candidate_intervention_actions:
                    if action_name in seen_actions:
                        continue
                    seen_actions.add(action_name)

                    spec = INTERVENTION_SPECS.get(action_name)
                    if not spec:
                        continue

                    # Evidence IDs come strictly from the supporting chunks of this relationship/pathway
                    ev_ids = rel.supporting_chunk_ids if rel.supporting_chunk_ids else pathway.evidence_ids

                    interventions.append(
                        CandidateIntervention(
                            action=spec["action"],
                            rationale=spec["rationale"],
                            affected_metrics=spec["affected_metrics"],
                            time_horizon=spec["time_horizon"],
                            required_conditions=spec["required_conditions"],
                            evidence_ids=ev_ids,
                            contraindications=spec.get("contraindications", []),
                        )
                    )

        return interventions
