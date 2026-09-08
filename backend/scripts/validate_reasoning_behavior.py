"""Behavioral validation script for Phase 7 Multi-Metric Ecological Reasoning Engine."""
import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.knowledge.indexer import InvertedIndex
from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.reasoning.context import ContextMatcher
from app.reasoning.engine import EcologicalReasoningEngine
from app.reasoning.models import (
    ContextMatchResult,
    EvidenceSupportedRelationship,
    ReasoningPathway,
    ReasoningResult,
    RelationshipSupportStatus,
)
from app.retrieval.hybrid import HybridRetriever
from app.schemas.state import (
    EnvironmentalState,
    EnvironmentalVariable,
    ProvenanceSource,
    VariableConfidence,
)


def run_behavioral_validation():
    print("=" * 80)
    print("PHASE 7 BEHAVIORAL VALIDATION: ECOLOGICAL REASONING ENGINE")
    print("=" * 80)

    # 1. Initialize engine with production store, index, and retriever
    db_path = REPO_ROOT / "data/knowledge.db"
    index_path = REPO_ROOT / "data/lexical_index.json"
    store = KnowledgeStore(db_path=db_path)
    index = InvertedIndex.load_from_file(index_path)
    retriever = HybridRetriever(store, index)
    engine = EcologicalReasoningEngine(retriever=retriever)

    # -------------------------------------------------------------------------
    # BEHAVIORAL SCENARIO 1: Canonical Challenge Scenario
    # Semi-arid wheat monoculture, 0.3% SOC, low rainfall
    # -------------------------------------------------------------------------
    print("\n[SCENARIO 1: Canonical Semi-Arid Monoculture (Challenge P0)]")
    print("-" * 80)

    state1 = EnvironmentalState()
    state1.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state1.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state1.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    state1.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)
    state1.climate.rainfall = EnvironmentalVariable(value="low", source=ProvenanceSource.USER)

    result1: ReasoningResult = engine.reason("conv-scenario-1", state1)

    print(f"1. Variables Considered ({len(result1.variables_considered)}):")
    for v in result1.variables_considered:
        print(f"   - {v.path}: {v.value}{' ' + v.unit if v.unit else ''} [{v.source.value}, {v.confidence.value}]")

    print(f"\n2. Scientific Sufficiency:")
    print(f"   - Is Sufficient: {result1.scientific_sufficiency.is_scientifically_sufficient}")
    print(f"   - Identified Domains: {result1.scientific_sufficiency.identified_domains}")
    print(f"   - Notes: {result1.scientific_sufficiency.evaluation_notes}")

    print(f"\n3. Evidence-Supported Relationships ({len(result1.evidence_supported_relationships)}):")
    for r in result1.evidence_supported_relationships:
        print(f"   * Edge: {r.source_variable} -> {r.target_variable}")
        print(f"     Mechanism: {r.mechanism}")
        print(f"     Supporting Chunks ({len(r.supporting_chunk_ids)}): {r.supporting_chunk_ids}")
        print(f"     Sources: {r.supporting_source_ids}")
        print(f"     Context Status: {r.context_match.is_compatible} ({r.context_match.matched_conditions})")

    print(f"\n4. Active Sequential Pathways (>= 3 Variables) ({len(result1.active_pathways)}):")
    for p in result1.active_pathways:
        print(f"   >>> Pathway: {p.pathway_id}")
        print(f"       Title: {p.title}")
        print(f"       Variables: {' -> '.join(p.participating_variables)}")
        print(f"       Edges ({len(p.ordered_relationships)}):")
        for e in p.ordered_relationships:
            print(f"         - {e.source_variable} -> {e.target_variable} [{', '.join(e.supporting_source_ids)}]")
        print(f"       Evidence IDs: {p.evidence_ids}")

    print(f"\n5. Candidate Interventions ({len(result1.candidate_interventions)}):")
    for i in result1.candidate_interventions:
        print(f"   + Action: {i.action}")
        print(f"     Why: {i.rationale}")
        print(f"     Affected Metrics: {i.affected_metrics}")
        print(f"     Horizon: {i.time_horizon}")
        print(f"     Evidence IDs: {i.evidence_ids}")
        print(f"     Contraindications: {i.contraindications}")

    assert result1.scientific_sufficiency.is_scientifically_sufficient is True
    assert len(result1.active_pathways) >= 1
    assert len(result1.candidate_interventions) >= 1
    print("\n>>> SCENARIO 1 BEHAVIORAL CHECK: PASSED")

    # -------------------------------------------------------------------------
    # BEHAVIORAL SCENARIO 2: Disconnected 3 Variables
    # Temperature 31C, Rainfall 800mm, Crop wheat
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[SCENARIO 2: Disconnected 3 Variables (Sufficiency Gate Test)]")
    print("-" * 80)

    state2 = EnvironmentalState()
    state2.climate.temperature = EnvironmentalVariable(value=31.0, unit="C", source=ProvenanceSource.USER)
    state2.climate.rainfall = EnvironmentalVariable(value=800.0, unit="mm", source=ProvenanceSource.USER)
    state2.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)

    result2: ReasoningResult = engine.reason("conv-scenario-2", state2)

    print(f"1. Variables Count: {len(result2.variables_considered)} (>= 3 variables)")
    print(f"2. Scientific Sufficiency:")
    print(f"   - Is Sufficient: {result2.scientific_sufficiency.is_scientifically_sufficient}")
    print(f"   - Missing Critical Context: {result2.scientific_sufficiency.missing_critical_context}")
    print(f"3. Active Pathways: {len(result2.active_pathways)} (must be 0)")
    print(f"4. Candidate Interventions: {len(result2.candidate_interventions)} (must be 0)")

    assert result2.scientific_sufficiency.is_scientifically_sufficient is False
    assert len(result2.active_pathways) == 0
    assert len(result2.candidate_interventions) == 0
    print("\n>>> SCENARIO 2 BEHAVIORAL CHECK: PASSED (Correctly halted with zero fabricated claims)")

    # -------------------------------------------------------------------------
    # BEHAVIORAL SCENARIO 3: Context Mismatch
    # Humid Tropical Orchard with High SOC
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[SCENARIO 3: Context Mismatch (Humid Tropical vs. Dryland Templates)]")
    print("-" * 80)

    state3 = EnvironmentalState()
    state3.region = EnvironmentalVariable(value="tropical", source=ProvenanceSource.USER)
    state3.soil.organic_carbon = EnvironmentalVariable(value=2.8, unit="%", source=ProvenanceSource.USER)
    state3.land_use.land_cover = EnvironmentalVariable(value="orchard", source=ProvenanceSource.USER)
    state3.climate.rainfall = EnvironmentalVariable(value="high", source=ProvenanceSource.USER)

    result3: ReasoningResult = engine.reason("conv-scenario-3", state3)

    print(f"1. Unsupported Relationships ({len(result3.unsupported_relationships)}):")
    for ur in result3.unsupported_relationships:
        print(f"   - Template: {ur.template_id} [{ur.support_status.value}]")
        print(f"     Reasons: {ur.validation_notes}")

    # Verify that dryland-specific templates were rejected due to context mismatch
    dryland_mismatches = [
        ur for ur in result3.unsupported_relationships
        if ur.support_status == RelationshipSupportStatus.UNSUPPORTED_CONTEXT_MISMATCH
    ]
    print(f"2. Context Mismatches Detected: {len(dryland_mismatches)}")
    assert len(dryland_mismatches) > 0
    print("\n>>> SCENARIO 3 BEHAVIORAL CHECK: PASSED (Correctly prevented out-of-context dryland templates)")

    # -------------------------------------------------------------------------
    # BEHAVIORAL SCENARIO 4: Sequential Integrity Verification
    # Demonstrating no fabricated A -> B -> C from A -> B and A -> C
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[SCENARIO 4: Sequential Integrity Gate]")
    print("-" * 80)

    rel_ab = EvidenceSupportedRelationship(
        relationship_id="REL-MOCK-1",
        template_id="TPL-MOCK-1",
        source_variable="land_use.land_cover",
        target_variable="soil.organic_carbon",
        mechanism="Monoculture depletes SOC",
        supporting_chunk_ids=["CHK-01"],
        supporting_source_ids=["SRC-01"],
        evidence_excerpts=["Mock excerpt 1"],
        context_match=ContextMatchResult(is_compatible=True),
        support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
        validation_notes="Valid",
    )
    rel_ac = EvidenceSupportedRelationship(
        relationship_id="REL-MOCK-2",
        template_id="TPL-MOCK-2",
        source_variable="land_use.land_cover",
        target_variable="biodiversity.pollinator_abundance",
        mechanism="Monoculture reduces pollinators",
        supporting_chunk_ids=["CHK-02"],
        supporting_source_ids=["SRC-02"],
        evidence_excerpts=["Mock excerpt 2"],
        context_match=ContextMatchResult(is_compatible=True),
        support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
        validation_notes="Valid",
    )

    divergent_pathways = engine._assemble_sequential_pathways([rel_ab, rel_ac], EnvironmentalState())
    print(f"Divergent edges (A->B, A->C) pathway count: {len(divergent_pathways)} (must be 0)")
    assert len(divergent_pathways) == 0

    rel_bc = EvidenceSupportedRelationship(
        relationship_id="REL-MOCK-3",
        template_id="TPL-MOCK-3",
        source_variable="soil.organic_carbon",
        target_variable="climate.rainfall",
        mechanism="SOC improves available water capacity",
        supporting_chunk_ids=["CHK-03"],
        supporting_source_ids=["SRC-03"],
        evidence_excerpts=["Mock excerpt 3"],
        context_match=ContextMatchResult(is_compatible=True),
        support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
        validation_notes="Valid",
    )

    sequential_pathways = engine._assemble_sequential_pathways([rel_ab, rel_bc], EnvironmentalState())
    print(f"Sequential edges (A->B, B->C) pathway count: {len(sequential_pathways)}")
    print(f"Sequential Pathway Variables: {' -> '.join(sequential_pathways[0].participating_variables)}")
    assert len(sequential_pathways) == 1
    assert sequential_pathways[0].participating_variables == ["land_use.land_cover", "soil.organic_carbon", "climate.rainfall"]
    print("\n>>> SCENARIO 4 BEHAVIORAL CHECK: PASSED (Sequential edge integrity strictly enforced)")

    print("\n" + "=" * 80)
    print("ALL 4 BEHAVIORAL VALIDATION SCENARIOS SUCCESSFULLY COMPLETED!")
    print("=" * 80)


if __name__ == "__main__":
    run_behavioral_validation()
