"""Phase 7 tests for multi-metric ecological reasoning, evidence gating, and anti-hallucination."""
import pytest
from pathlib import Path

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
    RelationshipTemplate,
)
from app.reasoning.sufficiency import ScientificSufficiencyEvaluator
from app.reasoning.templates import RELATIONSHIP_TEMPLATES
from app.retrieval.hybrid import HybridRetriever
from app.schemas.evidence import CandidateIntervention
from app.schemas.state import (
    EnvironmentalState,
    EnvironmentalVariable,
    ProvenanceSource,
    VariableConfidence,
)


@pytest.fixture(scope="module")
def shared_knowledge():
    """Loads production KnowledgeStore, InvertedIndex, and HybridRetriever."""
    db_path = REPO_ROOT / "data/knowledge.db"
    index_path = REPO_ROOT / "data/lexical_index.json"
    store = KnowledgeStore(db_path=db_path)
    index = InvertedIndex.load_from_file(index_path)
    retriever = HybridRetriever(store, index)
    return store, index, retriever


@pytest.fixture
def reasoning_engine(shared_knowledge):
    """Provides a fresh EcologicalReasoningEngine instance."""
    store, index, retriever = shared_knowledge
    return EcologicalReasoningEngine(retriever=retriever)


def test_scientific_sufficiency_gate(reasoning_engine):
    """
    Verify the scientific sufficiency gate enforces:
    3 variables != automatically enough information.
    Temperature + rainfall + crop is rejected, while a coherent nexus is approved.
    """
    # Case A: 3 disconnected variables (climate + crop, no soil or management practice)
    sparse_state = EnvironmentalState()
    sparse_state.climate.temperature = EnvironmentalVariable(value=31.0, unit="C", source=ProvenanceSource.USER)
    sparse_state.climate.rainfall = EnvironmentalVariable(value=800.0, unit="mm", source=ProvenanceSource.USER)
    sparse_state.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)

    result_sparse = reasoning_engine.reason("conv-sparse", sparse_state)
    assert result_sparse.scientific_sufficiency.is_scientifically_sufficient is False
    assert len(result_sparse.active_pathways) == 0
    assert len(result_sparse.candidate_interventions) == 0
    assert any("crop alone is scientifically insufficient" in note for note in result_sparse.limitations)

    # Case B: Coherent nexus (Soil condition + Climate regime + Land management)
    coherent_state = EnvironmentalState()
    coherent_state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    coherent_state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    coherent_state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    coherent_state.climate.rainfall = EnvironmentalVariable(value="low", source=ProvenanceSource.USER)

    result_coherent = reasoning_engine.reason("conv-coherent", coherent_state)
    assert result_coherent.scientific_sufficiency.is_scientifically_sufficient is True
    assert len(result_coherent.active_pathways) > 0


def test_multi_variable_reasoning_ge_3(reasoning_engine):
    """Verify that active reasoning pathways connect >= 3 distinct environmental variables."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    state.climate.rainfall = EnvironmentalVariable(value="low", source=ProvenanceSource.USER)

    result = reasoning_engine.reason("conv-ge3", state)
    assert len(result.active_pathways) >= 1

    for pathway in result.active_pathways:
        assert len(pathway.participating_variables) >= 3
        # Confirm variables are distinct
        assert len(set(pathway.participating_variables)) == len(pathway.participating_variables)
        assert pathway.support_status == RelationshipSupportStatus.EVIDENCE_SUPPORTED


def test_evidence_supported_relationships(reasoning_engine):
    """Verify that every edge in active pathways carries verified chunk IDs and source IDs."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)

    result = reasoning_engine.reason("conv-evidence", state)
    assert len(result.evidence_supported_relationships) > 0

    for rel in result.evidence_supported_relationships:
        assert rel.support_status == RelationshipSupportStatus.EVIDENCE_SUPPORTED
        assert len(rel.supporting_chunk_ids) > 0
        assert len(rel.supporting_source_ids) > 0
        for chunk_id in rel.supporting_chunk_ids:
            assert chunk_id.startswith("CHK-SRC-")
        for src_id in rel.supporting_source_ids:
            assert src_id.startswith("SRC-")


def test_no_fabricated_three_variable_chains(reasoning_engine):
    """
    Verify sequential integrity:
    Do not construct A -> B -> C from independent evidence for A -> B and A -> C.
    Only sequential chains (target of R1 == source of R2) may form a pathway.
    """
    # Construct mock relationships: A -> B and A -> C (divergent, not sequential)
    rel_ab = EvidenceSupportedRelationship(
        relationship_id="REL-AB",
        template_id="TPL-AB",
        source_variable="land_use.land_cover",
        target_variable="soil.organic_carbon",
        mechanism="Monoculture depletes SOC",
        supporting_chunk_ids=["CHK-01"],
        supporting_source_ids=["SRC-01"],
        evidence_excerpts=["Monoculture accelerates carbon loss"],
        context_match=ContextMatchResult(is_compatible=True),
        support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
        validation_notes="Mock AB",
    )
    rel_ac = EvidenceSupportedRelationship(
        relationship_id="REL-AC",
        template_id="TPL-AC",
        source_variable="land_use.land_cover",
        target_variable="biodiversity.pollinator_abundance",
        mechanism="Monoculture reduces pollinators",
        supporting_chunk_ids=["CHK-02"],
        supporting_source_ids=["SRC-02"],
        evidence_excerpts=["Pollinators decline without floral borders"],
        context_match=ContextMatchResult(is_compatible=True),
        support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
        validation_notes="Mock AC",
    )

    # Calling assembler on purely divergent edges [rel_ab, rel_ac] must NOT fabricate A -> B -> C
    state = EnvironmentalState()
    pathways = reasoning_engine._assemble_sequential_pathways([rel_ab, rel_ac], state)
    assert len(pathways) == 0, "Divergent edges A->B and A->C must not be chained into a sequential pathway A->B->C"

    # Now add genuine sequential edge B -> C (soil.organic_carbon -> climate.rainfall)
    rel_bc = EvidenceSupportedRelationship(
        relationship_id="REL-BC",
        template_id="TPL-BC",
        source_variable="soil.organic_carbon",
        target_variable="climate.rainfall",
        mechanism="Depleted SOC impairs available water holding capacity",
        supporting_chunk_ids=["CHK-03"],
        supporting_source_ids=["SRC-03"],
        evidence_excerpts=["SOC maintains available water capacity"],
        context_match=ContextMatchResult(is_compatible=True),
        support_status=RelationshipSupportStatus.EVIDENCE_SUPPORTED,
        validation_notes="Mock BC",
    )

    pathways_seq = reasoning_engine._assemble_sequential_pathways([rel_ab, rel_bc], state)
    assert len(pathways_seq) == 1
    assert pathways_seq[0].participating_variables == ["land_use.land_cover", "soil.organic_carbon", "climate.rainfall"]


def test_context_compatibility_layer():
    """Verify extensible ContextMatcher handles numeric ranges and taxonomic ontologies deterministically."""
    matcher = ContextMatcher()

    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)

    # Condition 1: Matches semi-arid dryland and SOC <= 1.1%
    cond1 = {
        "region": ["drylands", "semi-arid"],
        "soil.organic_carbon": {"lte": 1.1},
        "land_use.land_cover": ["monoculture"],
    }
    res1 = matcher.match(state, cond1)
    assert res1.is_compatible is True

    # Condition 2: Violates numeric threshold (requires SOC >= 2.0%)
    cond2 = {
        "soil.organic_carbon": {"gte": 2.0},
    }
    res2 = matcher.match(state, cond2)
    assert res2.is_compatible is False
    assert len(res2.unmatched_conditions) == 1

    # Condition 3: Violates region (requires tropical wetland)
    cond3 = {
        "region": ["tropical", "humid_tropics"],
    }
    res3 = matcher.match(state, cond3)
    assert res3.is_compatible is False


def test_relationship_specific_evidence_scope(reasoning_engine):
    """Verify that evidence retrieved for soil carbon cannot substantiate unrelated edges like pollinators."""
    # Create template for pollinators but restrict topics to soil_health (scope mismatch)
    tpl_mismatch = RelationshipTemplate(
        template_id="TPL-TEST-SCOPE-MISMATCH",
        source_variable="land_use.land_cover",
        target_variable="biodiversity.pollinator_abundance",
        mechanism_pattern="Floral borders benefit pollinators",
        required_topics=["soil_health"],  # Incompatible topic scope for pollinator edge
        required_terms=["pollinator", "density"],
        directional_indicators=["enhanc"],
        applicable_conditions={"land_use.land_cover": ["monoculture"]},
    )

    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)

    # Retrieve real chunks
    chunks = reasoning_engine._perform_multi_query_retrieval(state, ["soil_climate_management"])
    # Filtering with tpl_mismatch must return empty because soil chunks do not match pollinator terms
    matched = reasoning_engine._find_substantiating_chunks(tpl_mismatch, chunks)
    assert len(matched) == 0


def test_evidence_supported_vs_merely_evidence_present(reasoning_engine):
    """
    Verify that a chunk appearing in the top-k results is rejected if it does not
    contain the required terms and directional mechanism indicators.
    """
    tpl_strict = RelationshipTemplate(
        template_id="TPL-STRICT-CHECK",
        source_variable="soil.organic_carbon",
        target_variable="climate.rainfall",
        mechanism_pattern="SOC governs water retention",
        required_topics=["soil_health"],
        required_terms=["quantum_superposition_in_soil"],  # Non-existent term in corpus
        directional_indicators=["water capacity"],
        applicable_conditions={},
    )

    state = EnvironmentalState()
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)

    chunks = reasoning_engine._perform_multi_query_retrieval(state, ["soil_climate_management"])
    assert len(chunks) > 0  # Chunks are present in retrieval pool

    # But the template mechanism is not substantiated
    substantiated = reasoning_engine._find_substantiating_chunks(tpl_strict, chunks)
    assert len(substantiated) == 0


def test_anti_hallucination_t009_no_evidence_no_relationship(reasoning_engine):
    """
    T-009 Anti-Hallucination:
    A relationship with no supporting corpus evidence must be rejected and marked UNSUPPORTED_NO_EVIDENCE.
    It must never be incorporated into active reasoning pathways.
    """
    hallucinated_template = RelationshipTemplate(
        template_id="TPL-LUNAR-PHASE-SOIL-CARBON",
        source_variable="soil.organic_carbon",
        target_variable="climate.temperature",
        mechanism_pattern="Lunar gravitational cycles dictate soil carbon respiration rates.",
        required_topics=["astronomy"],
        required_terms=["lunar_phase", "gravitational_pull"],
        directional_indicators=["dictat"],
        applicable_conditions={},
    )

    engine_with_hallucinated_tpl = EcologicalReasoningEngine(
        retriever=reasoning_engine.retriever,
        templates=RELATIONSHIP_TEMPLATES + [hallucinated_template],
    )

    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)

    result = engine_with_hallucinated_tpl.reason("conv-t009", state)

    # Hallucinated relationship must be rejected
    unsupported_ids = [r.template_id for r in result.unsupported_relationships]
    assert "TPL-LUNAR-PHASE-SOIL-CARBON" in unsupported_ids

    # Must NOT appear in active pathways
    for pathway in result.active_pathways:
        for rel in pathway.ordered_relationships:
            assert rel.template_id != "TPL-LUNAR-PHASE-SOIL-CARBON"


def test_provenance_propagation(reasoning_engine):
    """Verify that provenance (USER, STRUCTURED_INPUT, etc.) propagates cleanly into ReasoningVariable models."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(
        value="semi-arid",
        source=ProvenanceSource.STRUCTURED_INPUT,
        confidence=VariableConfidence.EXPLICIT,
    )
    state.soil.organic_carbon = EnvironmentalVariable(
        value=0.3,
        unit="%",
        source=ProvenanceSource.USER,
        confidence=VariableConfidence.EXPLICIT,
    )
    state.land_use.land_cover = EnvironmentalVariable(
        value="monoculture",
        source=ProvenanceSource.USER,
        confidence=VariableConfidence.EXPLICIT,
    )

    result = reasoning_engine.reason("conv-prov-prop", state)
    var_map = {v.path: v for v in result.variables_considered}

    assert var_map["region"].source == ProvenanceSource.STRUCTURED_INPUT
    assert var_map["soil.organic_carbon"].source == ProvenanceSource.USER
    assert var_map["land_use.land_cover"].source == ProvenanceSource.USER


def test_candidate_intervention_generation(reasoning_engine):
    """Verify candidate interventions have required fields, evidence IDs, contraindications, and no fabricated claims."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)

    result = reasoning_engine.reason("conv-interventions", state)
    assert len(result.candidate_interventions) > 0

    for item in result.candidate_interventions:
        assert isinstance(item, CandidateIntervention)
        assert len(item.action) > 0
        assert len(item.rationale) > 0
        assert len(item.affected_metrics) >= 1
        assert item.time_horizon in ["short", "medium", "long"]
        assert len(item.evidence_ids) >= 1
        for eid in item.evidence_ids:
            assert eid.startswith("CHK-SRC-")
        # Verify contraindications are explicitly listed
        assert isinstance(item.contraindications, list)
        assert len(item.contraindications) >= 1


def test_deterministic_offline_behavior(reasoning_engine):
    """Verify the reasoning engine executes with zero LLM and zero network calls, producing identical outputs."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)

    res1 = reasoning_engine.reason("conv-det", state)
    res2 = reasoning_engine.reason("conv-det", state)

    assert len(res1.active_pathways) == len(res2.active_pathways)
    assert len(res1.candidate_interventions) == len(res2.candidate_interventions)
    assert [p.pathway_id for p in res1.active_pathways] == [p.pathway_id for p in res2.active_pathways]


def test_behavioral_validation_canonical_challenge_scenario(reasoning_engine):
    """Behavioral test: Canonical semi-arid wheat monoculture with 0.3% SOC and low rainfall."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="monoculture", source=ProvenanceSource.USER)
    state.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)
    state.climate.rainfall = EnvironmentalVariable(value="low", source=ProvenanceSource.USER)

    result = reasoning_engine.reason("conv-canonical", state)

    # 1. Scientific sufficiency must pass
    assert result.scientific_sufficiency.is_scientifically_sufficient is True
    assert "soil_climate_management" in result.scientific_sufficiency.identified_domains

    # 2. Sequential pathway A -> B -> C must form
    assert len(result.active_pathways) == 1
    pathway = result.active_pathways[0]
    assert pathway.participating_variables == ["land_use.land_cover", "soil.organic_carbon", "climate.rainfall"]
    assert len(pathway.ordered_relationships) == 2
    assert "CHK-SRC-IPCC-2019-SRCCL-001" in pathway.evidence_ids
    assert "CHK-SRC-FAO-2017-SOILCARBON-001" in pathway.evidence_ids

    # 3. Interventions must include cover crops with moisture contraindications
    actions = [i.action for i in result.candidate_interventions]
    assert any("cover crops" in a.lower() for a in actions)
    cover_crop_item = next(i for i in result.candidate_interventions if "cover crops" in i.action.lower())
    assert any("moisture competition" in c.lower() for c in cover_crop_item.contraindications)


def test_behavioral_validation_tropical_context_mismatch(reasoning_engine):
    """Behavioral test: Humid tropical orchard rejects dryland templates via extensible ContextMatcher."""
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="tropical", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=2.8, unit="%", source=ProvenanceSource.USER)
    state.land_use.land_cover = EnvironmentalVariable(value="orchard", source=ProvenanceSource.USER)
    state.climate.rainfall = EnvironmentalVariable(value="high", source=ProvenanceSource.USER)

    result = reasoning_engine.reason("conv-tropical-mismatch", state)

    # Dryland templates must be rejected with UNSUPPORTED_CONTEXT_MISMATCH
    mismatches = [
        ur for ur in result.unsupported_relationships
        if ur.support_status == RelationshipSupportStatus.UNSUPPORTED_CONTEXT_MISMATCH
    ]
    assert len(mismatches) >= 2
    mismatch_tpl_ids = {ur.template_id for ur in mismatches}
    assert "TPL-MONOCULTURE-SOC-DEPLETION" in mismatch_tpl_ids
    assert "TPL-SOC-WATER-RETENTION" in mismatch_tpl_ids

