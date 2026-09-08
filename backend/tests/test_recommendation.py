"""Phase 8 tests for Recommendation Generation, Claim-Level Evidence Validation, and Traceability."""
import pytest
from pathlib import Path

from app.knowledge.indexer import InvertedIndex
from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.reasoning.engine import EcologicalReasoningEngine
from app.reasoning.models import ReasoningResult
from app.recommendation.evidence import EvidenceResolver
from app.recommendation.generator import RecommendationGenerator
from app.recommendation.models import (
    ClaimValidationRecord,
    ClaimValidationStatus,
    RecommendationItem,
    RecommendationResult,
    RejectedCandidate,
)
from app.recommendation.validator import EvidenceTraceabilityValidator, ValidationResult
from app.retrieval.hybrid import HybridRetriever
from app.schemas.evidence import CandidateIntervention
from app.schemas.recommendation import EvidenceStrength, TimeHorizon
from app.schemas.state import (
    EnvironmentalState,
    EnvironmentalVariable,
    ProvenanceSource,
    VariableConfidence,
)


@pytest.fixture(scope="module")
def knowledge_base():
    """Loads shared production KnowledgeStore, InvertedIndex, and HybridRetriever."""
    db_path = REPO_ROOT / "data/knowledge.db"
    index_path = REPO_ROOT / "data/lexical_index.json"
    store = KnowledgeStore(db_path=db_path)
    index = InvertedIndex.load_from_file(index_path)
    retriever = HybridRetriever(store, index)
    return store, index, retriever


@pytest.fixture
def reasoning_engine(knowledge_base):
    """Provides a Phase 7 EcologicalReasoningEngine."""
    store, index, retriever = knowledge_base
    return EcologicalReasoningEngine(retriever=retriever)


@pytest.fixture
def recommendation_generator(knowledge_base):
    """Provides a Phase 8 RecommendationGenerator."""
    store, index, retriever = knowledge_base
    resolver = EvidenceResolver(store=store)
    validator = EvidenceTraceabilityValidator(store=store, resolver=resolver)
    return RecommendationGenerator(store=store, validator=validator, resolver=resolver)


# =============================================================================
# 1. Evidence Resolution & Traceability Tests
# =============================================================================

def test_evidence_id_resolves_to_actual_chunk(knowledge_base):
    """Verify evidence ID resolves to a real chunk with full source metadata, URL, and DOI."""
    store, _, _ = knowledge_base
    resolver = EvidenceResolver(store=store)

    evidence_id = "CHK-SRC-FAO-2020-RECARB-001"
    items = resolver.resolve_evidence_items([evidence_id])

    assert len(items) == 1
    item = items[0]
    assert item.evidence_id == evidence_id
    assert item.source_id == "SRC-FAO-2020-RECARB"
    assert "FAO" in item.publisher
    assert item.year == 2020
    assert len(item.excerpt) > 20
    assert item.source_url is not None
    assert item.doi == "10.4060/ca9668en"


def test_recommendation_requires_evidence(recommendation_generator):
    """Verify a candidate intervention with missing or empty evidence IDs is rejected."""
    candidate_no_evid = CandidateIntervention(
        action="Apply biochar to soil",
        rationale="Biochar increases soil carbon storage.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="medium",
        required_conditions=["cropland"],
        evidence_ids=[],  # Empty evidence IDs
    )

    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)

    val_res = recommendation_generator.validator.validate_candidate(candidate_no_evid, state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "evidence"
    assert any(c.status == ClaimValidationStatus.UNSUPPORTED_NO_EVIDENCE for c in val_res.claim_records)


def test_unresolvable_evidence_id_rejected(recommendation_generator):
    """Verify an invented non-existent evidence ID is rejected."""
    candidate_fake_evid = CandidateIntervention(
        action="Introduce legume cover crops",
        rationale="Fixes nitrogen.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="medium",
        required_conditions=["cropland"],
        evidence_ids=["CHK-SRC-FAKE-PAPER-999-001"],  # Fabricated ID
    )

    state = EnvironmentalState()
    val_res = recommendation_generator.validator.validate_candidate(candidate_fake_evid, state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "evidence"


# =============================================================================
# 2. T-009: No Evidence -> No Claim & Mechanism-Specific Validation
# =============================================================================

def test_evidence_present_but_mechanism_unsupported_rejected(recommendation_generator):
    """
    Verify that top-k evidence discussing general topics does NOT validate an
    unsupported intervention action. Evidence relevance != evidence support.
    """
    # Cite FAO-2017 (Soil carbon potential) for an unrelated action: "Install solar panels"
    candidate_unsupported_action = CandidateIntervention(
        action="Install solar panels across farm fields",
        rationale="Generates renewable electricity for farm machinery.",
        affected_metrics=["energy.generation"],
        time_horizon="short",
        required_conditions=["cropland"],
        evidence_ids=["CHK-SRC-FAO-2017-SOILCARBON-001"],  # Real chunk, but discusses soil carbon, NOT solar panels
    )

    state = EnvironmentalState()
    val_res = recommendation_generator.validator.validate_candidate(candidate_unsupported_action, state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "mechanism"
    assert any(c.status == ClaimValidationStatus.UNSUPPORTED_CLAIM for c in val_res.claim_records)


def test_t009_unsupported_candidate_never_in_final_recommendations(recommendation_generator):
    """Verify that an unsupported candidate intervention is never returned as a RecommendationItem."""
    candidate_bad = CandidateIntervention(
        action="Aerate deep soil with heavy diesel plows",
        rationale="Deep compaction relief improves soil life.",
        affected_metrics=["soil.compaction"],
        time_horizon="short",
        required_conditions=[],
        evidence_ids=[],
    )

    # Wrap in synthetic ReasoningResult
    from app.reasoning.models import ScientificSufficiencyResult, ReasoningPathway
    reasoning_res = ReasoningResult(
        conversation_id="conv-t009-rec",
        variables_considered=[],
        scientific_sufficiency=ScientificSufficiencyResult(
            is_scientifically_sufficient=True,
            identified_domains=["soil_climate_management"],
            matched_templates=[],
            missing_critical_context=[],
            evaluation_notes="Mock",
        ),
        active_pathways=[
            ReasoningPathway(
                pathway_id="PATH-MOCK",
                title="Mock Pathway",
                participating_variables=["soil.organic_carbon", "land_use.land_cover", "soil.moisture"],
                ordered_relationships=[],
                evidence_ids=["CHK-SRC-FAO-2020-RECARB-001"],
            )
        ],
        candidate_interventions=[candidate_bad],
    )

    state = EnvironmentalState()
    res = recommendation_generator.generate("conv-t009-rec", reasoning_res, state)

    assert len(res.recommendations) == 0
    assert len(res.rejected_candidates) == 1
    assert res.rejected_candidates[0].candidate_action == candidate_bad.action


# =============================================================================
# 3. Quantitative Claim Firewall Tests
# =============================================================================

def test_unsupported_quantitative_claim_rejected(recommendation_generator):
    """
    Verify the quantitative firewall:
    A candidate claiming an unverified number (e.g. 'increases biodiversity by 99%')
    where 99% is absent from the cited evidence chunk is rejected.
    """
    candidate_fake_number = CandidateIntervention(
        action="Introduce legume cover crops into rotation",
        rationale="Builds soil organic carbon and boosts total farm yield by 99% without irrigation.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="medium",
        required_conditions=["semi-arid drylands"],
        evidence_ids=["CHK-SRC-FAO-2020-RECARB-001"],  # Chunk does NOT say 99%
    )

    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)

    val_res = recommendation_generator.validator.validate_candidate(candidate_fake_number, state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "quantitative"
    assert any(c.status == ClaimValidationStatus.QUANTITATIVE_CLAIM_UNSUPPORTED for c in val_res.claim_records)


def test_supported_quantitative_claim_preserved(recommendation_generator):
    """
    Verify the quantitative firewall:
    A candidate claiming an exact number present in the cited evidence chunk (e.g. '30% crop residue')
    is approved.
    """
    candidate_verified_number = CandidateIntervention(
        action="Retain at least 30% crop residue on soil surface",
        rationale="Leaving at least 30% crop residue on the surface moderates soil temperature by 2-5 degrees Celsius and preserves soil moisture.",
        affected_metrics=["soil.organic_carbon", "soil.moisture"],
        time_horizon="short",
        required_conditions=["cropland"],
        evidence_ids=["CHK-SRC-FAO-2020-RECARB-002"],  # CHK-SRC-FAO-2020-RECARB-002 explicitly contains '30%' and '2-5 degrees'
    )

    state = EnvironmentalState()
    state.land_use.land_cover = EnvironmentalVariable(value="cropland", source=ProvenanceSource.USER)

    val_res = recommendation_generator.validator.validate_candidate(candidate_verified_number, state)
    assert val_res.is_valid is True
    assert any(c.status == ClaimValidationStatus.SUPPORTED and "30%" in c.claim_text for c in val_res.claim_records)


# =============================================================================
# 4. Context & Contraindication Validation Tests
# =============================================================================

def test_context_mismatch_rejects_candidate(recommendation_generator):
    """Verify that a dryland recommendation is rejected when evaluated against a humid tropical state."""
    dryland_candidate = CandidateIntervention(
        action="Introduce legume cover crops into rotation",
        rationale="Builds soil organic carbon pools in drylands.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="medium",
        required_conditions=["semi-arid drylands", "baseline SOC < 1.0%"],
        evidence_ids=["CHK-SRC-FAO-2020-RECARB-001"],
    )

    # Incompatible tropical state with high SOC
    tropical_state = EnvironmentalState()
    tropical_state.region = EnvironmentalVariable(value="tropical", source=ProvenanceSource.USER)
    tropical_state.soil.organic_carbon = EnvironmentalVariable(value=2.5, unit="%", source=ProvenanceSource.USER)

    val_res = recommendation_generator.validator.validate_candidate(dryland_candidate, tropical_state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "context"
    assert any(c.status == ClaimValidationStatus.CONTEXT_MISMATCH for c in val_res.claim_records)


def test_blocking_contraindication_rejects_candidate(recommendation_generator):
    """
    Verify contraindication validation:
    When user state has rainfall < 300 mm, cover crops contraindication
    (< 300 mm moisture competition) is active and blocking -> candidate rejected.
    """
    cover_crop_candidate = CandidateIntervention(
        action="Introduce legume cover crops into rotation",
        rationale="Builds soil organic carbon pools.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="medium",
        required_conditions=["semi-arid drylands"],
        evidence_ids=["CHK-SRC-FAO-2020-RECARB-001"],
        contraindications=[
            "In regions with severe annual rainfall deficits (< 300 mm/year), unmanaged cover crop biomass may cause seasonal soil moisture competition; terminate cover crops early before crop sowing."
        ],
    )

    # State with severe drought (rainfall = 200 mm/year < 300 mm threshold)
    arid_state = EnvironmentalState()
    arid_state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    arid_state.climate.rainfall = EnvironmentalVariable(value=200.0, unit="mm/year", source=ProvenanceSource.USER)

    val_res = recommendation_generator.validator.validate_candidate(cover_crop_candidate, arid_state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "contraindication"
    assert any(c.status == ClaimValidationStatus.CONTRAINDICATION_BLOCKED for c in val_res.claim_records)


def test_non_blocking_contraindication_preserved_as_limitation(recommendation_generator):
    """
    Verify contraindication validation:
    When user state has rainfall 450 mm (not < 300 mm), the contraindication is NOT blocking,
    but is preserved as an explicit cautionary limitation.
    """
    cover_crop_candidate = CandidateIntervention(
        action="Introduce legume cover crops into rotation",
        rationale="Builds soil organic carbon pools.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="medium",
        required_conditions=["semi-arid drylands"],
        evidence_ids=["CHK-SRC-FAO-2020-RECARB-001"],
        contraindications=[
            "In regions with severe annual rainfall deficits (< 300 mm/year), unmanaged cover crop biomass may cause seasonal soil moisture competition."
        ],
    )

    # State with moderate rainfall (450 mm/year > 300 mm)
    semi_arid_state = EnvironmentalState()
    semi_arid_state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    semi_arid_state.climate.rainfall = EnvironmentalVariable(value=450.0, unit="mm/year", source=ProvenanceSource.USER)

    val_res = recommendation_generator.validator.validate_candidate(cover_crop_candidate, semi_arid_state)
    assert val_res.is_valid is True
    assert len(val_res.active_contraindications) == 1
    assert any("Cautionary Condition" in lim for lim in val_res.limitations)


# =============================================================================
# 5. Full End-to-End Canonical Pipeline Test (Section 15)
# =============================================================================

def test_canonical_end_to_end_recommendation_pipeline(reasoning_engine, recommendation_generator):
    """
    Full Canonical Pipeline (Section 15):
    Input: Semi-arid wheat monoculture with 0.3% SOC and low rainfall.
    Pipeline:
      Environmental State
      -> Phase 4 Hybrid Retrieval
      -> Phase 7 Reasoning & Scientific Sufficiency
      -> Supported Sequential Pathways (>= 3 variables)
      -> Candidate Interventions
      -> Phase 8 Evidence Resolution & Claim Validation
      -> Final Verified RecommendationItem records.
    """
    conv_id = "conv-canonical-p8"
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    state.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)
    state.climate.rainfall = EnvironmentalVariable(value="low", source=ProvenanceSource.USER)

    # 1. Phase 7 Reasoning
    reasoning_res: ReasoningResult = reasoning_engine.reason(conv_id, state)
    assert reasoning_res.scientific_sufficiency.is_scientifically_sufficient is True
    assert len(reasoning_res.active_pathways) >= 1
    assert len(reasoning_res.candidate_interventions) >= 1

    # 2. Phase 8 Recommendation Generation & Validation
    rec_res: RecommendationResult = recommendation_generator.generate(conv_id, reasoning_res, state)

    assert rec_res.evidence_validation_passed is True
    assert len(rec_res.recommendations) >= 1

    # Inspect the primary recommendation
    first_rec: RecommendationItem = rec_res.recommendations[0]
    assert first_rec.recommendation_id.startswith("REC-")
    assert len(first_rec.action) > 0
    assert len(first_rec.rationale) > 0
    assert first_rec.why == first_rec.rationale
    assert len(first_rec.impacted_metrics) >= 1
    assert first_rec.time_horizon in [TimeHorizon.SHORT, TimeHorizon.MEDIUM, TimeHorizon.LONG]
    assert len(first_rec.evidence_ids) >= 1
    assert len(first_rec.source_ids) >= 1
    assert first_rec.evidence_strength in [EvidenceStrength.STRONG, EvidenceStrength.MODERATE]
    assert len(first_rec.evidence) >= 1

    # Verify resolved evidence traceability chain
    first_ev = first_rec.evidence[0]
    assert first_ev.evidence_id == first_rec.evidence_ids[0]
    assert first_ev.source_id in first_rec.source_ids
    assert len(first_ev.title) > 0
    assert len(first_ev.publisher) > 0
    assert first_ev.source_url is not None

    # Verify supporting pathway IDs
    assert len(first_rec.supporting_pathway_ids) >= 1
    assert "PATH-" in first_rec.supporting_pathway_ids[0]

    # Verify claim validation records exist and all passed
    assert len(first_rec.claim_validations) >= 1
    assert all(cv.status == ClaimValidationStatus.SUPPORTED for cv in first_rec.claim_validations if cv.claim_type != "contraindication")

    # Verify limitations include active contraindications
    assert len(first_rec.limitations) >= 1


# =============================================================================
# 6. Negative End-to-End Tests (Sections 16 & 17)
# =============================================================================

def test_negative_end_to_end_disconnected_variables(reasoning_engine, recommendation_generator):
    """
    Negative Test 1 (Section 16):
    Temperature = 31C, Rainfall = 800 mm, Crop = wheat.
    Scientific sufficiency = False -> 0 pathways -> 0 candidate interventions -> 0 recommendations.
    """
    state_sparse = EnvironmentalState()
    state_sparse.climate.temperature = EnvironmentalVariable(value=31.0, unit="C", source=ProvenanceSource.USER)
    state_sparse.climate.rainfall = EnvironmentalVariable(value=800.0, unit="mm", source=ProvenanceSource.USER)
    state_sparse.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)

    reasoning_res = reasoning_engine.reason("conv-neg-1", state_sparse)
    assert reasoning_res.scientific_sufficiency.is_scientifically_sufficient is False

    rec_res = recommendation_generator.generate("conv-neg-1", reasoning_res, state_sparse)
    assert len(rec_res.recommendations) == 0
    assert len(rec_res.rejected_candidates) == 0
    assert any("crop alone is scientifically insufficient" in lim for lim in rec_res.limitations)


def test_negative_end_to_end_context_mismatch(reasoning_engine, recommendation_generator):
    """
    Negative Test 2 (Section 17):
    Region = tropical, SOC = 2.8%, Land use = orchard, Rainfall = high.
    Dryland-specific templates must not activate.
    """
    tropical_state = EnvironmentalState()
    tropical_state.region = EnvironmentalVariable(value="tropical", source=ProvenanceSource.USER)
    tropical_state.soil.organic_carbon = EnvironmentalVariable(value=2.8, unit="%", source=ProvenanceSource.USER)
    tropical_state.land_use.land_cover = EnvironmentalVariable(value="orchard", source=ProvenanceSource.USER)
    tropical_state.climate.rainfall = EnvironmentalVariable(value="high", source=ProvenanceSource.USER)

    reasoning_res = reasoning_engine.reason("conv-neg-2", tropical_state)
    # Dryland pathways must be 0
    assert len(reasoning_res.active_pathways) == 0

    rec_res = recommendation_generator.generate("conv-neg-2", reasoning_res, tropical_state)
    assert len(rec_res.recommendations) == 0
