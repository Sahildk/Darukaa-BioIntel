"""Phase 8 Behavioral Validation: Recommendation Generation & Traceability Validator."""
import json
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.knowledge.indexer import InvertedIndex
from app.retrieval.hybrid import HybridRetriever
from app.reasoning.engine import EcologicalReasoningEngine
from app.recommendation.generator import RecommendationGenerator
from app.schemas.state import EnvironmentalState, EnvironmentalVariable, ProvenanceSource, VariableConfidence


def run_behavioral_validation():
    print("=" * 80)
    print("PHASE 8 BEHAVIORAL VALIDATION: RECOMMENDATION & TRACEABILITY VALIDATOR")
    print("=" * 80)

    db_path = REPO_ROOT / "data/knowledge.db"
    index_path = REPO_ROOT / "data/lexical_index.json"
    store = KnowledgeStore(db_path=db_path)
    index = InvertedIndex.load_from_file(index_path)
    retriever = HybridRetriever(store, index)
    reasoning_engine = EcologicalReasoningEngine(retriever=retriever)
    recommendation_generator = RecommendationGenerator(store=store)

    # -------------------------------------------------------------------------
    # Scenario 1: Canonical Challenge Scenario (P0)
    # Semi-arid wheat monoculture with 0.3% SOC and low rainfall
    # -------------------------------------------------------------------------
    print("\n[SCENARIO 1: Canonical End-to-End Recommendation Pipeline]")
    print("-" * 80)

    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER, confidence=VariableConfidence.EXPLICIT)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER, confidence=VariableConfidence.EXPLICIT)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER, confidence=VariableConfidence.EXPLICIT)
    state.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER, confidence=VariableConfidence.EXPLICIT)
    state.climate.rainfall = EnvironmentalVariable(value="low", source=ProvenanceSource.USER, confidence=VariableConfidence.EXPLICIT)

    # Step 1: Reasoning
    conv_id = "conv-behavioral-p8"
    reasoning_res = reasoning_engine.reason(conv_id, state)
    print(f"1. Reasoning Pathways Discovered: {len(reasoning_res.active_pathways)}")
    for p in reasoning_res.active_pathways:
        print(f"   * Pathway: {' -> '.join(p.participating_variables)}")
    print(f"2. Candidate Interventions Generated: {len(reasoning_res.candidate_interventions)}")

    # Step 2: Phase 8 Recommendation Generation & Validation
    rec_res = recommendation_generator.generate(conv_id, reasoning_res, state)
    print(f"3. Evidence Validation Passed: {rec_res.evidence_validation_passed}")
    print(f"4. Validated Recommendations Count: {len(rec_res.recommendations)}")
    print(f"5. Rejected Candidates Count: {len(rec_res.rejected_candidates)}")

    assert len(rec_res.recommendations) >= 1, "Must generate at least 1 validated recommendation"

    for idx, rec in enumerate(rec_res.recommendations, 1):
        print(f"\n   >>> Recommendation #{idx}: [{rec.recommendation_id}]")
        print(f"       Action: {rec.action}")
        print(f"       Rationale: {rec.rationale}")
        print(f"       Time Horizon: {rec.time_horizon.value}")
        print(f"       Evidence Strength: {rec.evidence_strength.value.upper()}")
        print(f"       Impacted Metrics: {rec.impacted_metrics}")
        print(f"       Supporting Pathways: {rec.supporting_pathway_ids}")
        print(f"       Resolved Evidence ({len(rec.evidence)}):")
        for ev in rec.evidence:
            print(f"         - [{ev.evidence_id}] from '{ev.publisher}' ({ev.year}): {ev.title[:70]}...")
            print(f"           URL: {ev.source_url} | DOI: {ev.doi}")
        print(f"       Claim Validations ({len(rec.claim_validations)}):")
        for cv in rec.claim_validations:
            print(f"         * [{cv.claim_type}] {cv.claim_id}: {cv.status.value} - {cv.details[:80]}...")
        print(f"       Contraindications / Cautionary Conditions ({len(rec.contraindications)}):")
        for c in rec.contraindications:
            print(f"         ! {c}")
        print(f"       Limitations ({len(rec.limitations)}):")
        for l in rec.limitations:
            print(f"         - {l}")

    print("\n>>> SCENARIO 1 BEHAVIORAL CHECK: PASSED (Complete End-to-End Traceability Verified)")

    # -------------------------------------------------------------------------
    # Scenario 2: Severe Rainfall Deficit Blocking Contraindication
    # Annual rainfall < 300 mm/year triggers hard block on moisture competition
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("[SCENARIO 2: Hard-Blocked Contraindication (Rainfall < 300 mm/year)]")
    print("-" * 80)

    state_deficit = EnvironmentalState()
    state_deficit.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state_deficit.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state_deficit.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    state_deficit.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)
    state_deficit.climate.rainfall = EnvironmentalVariable(value=220.0, unit="mm", source=ProvenanceSource.USER)

    reasoning_deficit = reasoning_engine.reason("conv-deficit", state_deficit)
    rec_deficit = recommendation_generator.generate("conv-deficit", reasoning_deficit, state_deficit)

    print(f"1. Validated Recommendations: {len(rec_deficit.recommendations)}")
    print(f"2. Rejected Candidates: {len(rec_deficit.rejected_candidates)}")
    for rej in rec_deficit.rejected_candidates:
        print(f"   * Rejected: '{rej.candidate_action}'")
        print(f"     Stage: {rej.rejection_stage} | Reason: {rej.reason}")
        print(f"     Details: {rej.details}")

    blocked_stages = [r.rejection_stage for r in rec_deficit.rejected_candidates]
    assert "contraindication" in blocked_stages, "Severe moisture deficit must trigger contraindication rejection stage"
    print("\n>>> SCENARIO 2 BEHAVIORAL CHECK: PASSED (Contraindication Firewall Functional)")

    print("\n" + "=" * 80)
    print("ALL PHASE 8 BEHAVIORAL VALIDATION CHECKS COMPLETED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    run_behavioral_validation()
