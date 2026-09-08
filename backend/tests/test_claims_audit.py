"""Scientific Claims Audit Test Suite.

Enforces the Phase 12 Scientific Claims Audit Checklist:
1. Every DOI / URL corresponds to an actual indexed source in the curated manifest.
2. No fabricated study, year, or publisher.
3. Every recommendation retains valid chunk IDs present in KnowledgeStore.
4. Quantitative claims must have verbatim evidence support.
5. Rainfall is treated as an exogenous climatic forcing (no relationship creates rainfall).
6. No recommendation bypasses the 4-gate evidence validator.
7. Evaluation scores are explicitly identified as internal hackathon-aligned benchmarks.
"""
from pathlib import Path
import re
import pytest

from app.knowledge.store import KnowledgeStore, REPO_ROOT, load_manifest
from app.reasoning.templates import RELATIONSHIP_TEMPLATES
from app.recommendation.validator import EvidenceTraceabilityValidator
from app.schemas.chat import ChatRequest, StructuredInput
from app.schemas.evidence import CandidateIntervention
from app.schemas.recommendation import RecommendationResponse
from app.services.conversation_service import EnvironmentalChatService
from app.schemas.state import EnvironmentalState


@pytest.fixture
def store():
    return KnowledgeStore(db_path=REPO_ROOT / "data/knowledge.db")


@pytest.fixture
def chat_service():
    return EnvironmentalChatService()


# =============================================================================
# 1. Manifest Provenance & Source Metadata Audit
# =============================================================================

def test_audit_manifest_sources_have_valid_doi_and_url(store):
    """
    Verify that every source in the curated corpus manifest contains valid, authentic
    scholarly metadata (DOI or official URL, real publisher, publication year).
    """
    manifest = load_manifest(REPO_ROOT / "data/corpus_manifest.json")
    assert len(manifest.sources) == 10

    for source in manifest.sources:
        # Title, publisher, year must be non-empty and realistic
        assert len(source.title.strip()) > 5
        assert len(source.publisher.strip()) > 1
        assert 1990 <= source.year <= 2024

        # Must have either a valid DOI or official publisher URL
        has_doi = source.doi is not None and ("10." in source.doi or "doi.org" in source.doi)
        has_url = source.source_url is not None and source.source_url.startswith("http")
        assert has_doi or has_url, f"Source {source.source_id} lacks authentic DOI or URL."

        # Document file must physically exist in data/corpus/
        doc_path = REPO_ROOT / "data/corpus" / source.rel_path
        assert doc_path.exists(), f"Source file missing for {source.source_id}: {doc_path}"


# =============================================================================
# 2. Traceability Audit: Recommendations Link to Authentic Indexed Chunks
# =============================================================================

def test_audit_no_fabricated_citations_in_recommendations(chat_service, store):
    """
    Verify that all evidence items produced during end-to-end execution link
    directly to real, authentic chunks and sources stored in KnowledgeStore.
    """
    payload = ChatRequest(
        conversation_id="audit-traceability",
        message="Wheat monoculture in semi-arid conditions with 0.3% SOC.",
        structured_input=StructuredInput(
            region="semi-arid",
            soil_organic_carbon=0.3,
            rainfall="low",
            crop="wheat",
            land_use="monoculture",
        ),
    )

    resp = chat_service.process_chat(payload)
    assert isinstance(resp, RecommendationResponse)
    assert len(resp.recommendations) >= 1

    manifest = load_manifest(REPO_ROOT / "data/corpus_manifest.json")
    valid_source_ids = {s.source_id for s in manifest.sources}

    for rec in resp.recommendations:
        assert len(rec.evidence) >= 1
        for ev in rec.evidence:
            # Source ID must be authentic
            assert ev.source_id in valid_source_ids

            # Chunk ID must physically exist in KnowledgeStore
            chunk_rec = store.get_chunk(ev.evidence_id)
            assert chunk_rec is not None
            assert chunk_rec["source_id"] == ev.source_id

            # Year and publisher must match indexed source
            assert ev.year == chunk_rec["year"]
            assert ev.publisher == chunk_rec["publisher"]


# =============================================================================
# 3. Quantitative Claim Audit: Unbacked Numbers Are Intercepted
# =============================================================================

def test_audit_quantitative_claims_have_verbatim_evidence_support(store):
    """
    Verify that the quantitative claim firewall intercepts effect sizes that
    do not appear verbatim in cited peer-reviewed chunks.
    """
    validator = EvidenceTraceabilityValidator(store=store)
    clean_state = EnvironmentalState()

    unbacked_candidate = CandidateIntervention(
        action="Introduce legume cover crops into rotation to achieve a 45% increase in soil organic carbon",
        rationale="Enhances microbial efficiency leading to a 45% gain.",
        affected_metrics=["soil.organic_carbon"],
        time_horizon="short",
        required_conditions=[],
        evidence_ids=["CHK-SRC-LAL-2004-SCIENCE-001"],
    )

    val_res = validator.validate_candidate(unbacked_candidate, clean_state)
    has_unsupported_quant = any(
        r.claim_type == "quantitative_claim" and r.status.value != "supported"
        for r in val_res.claim_records
    )
    assert val_res.is_valid is False or has_unsupported_quant
    assert any("45%" in r.claim_text for r in val_res.claim_records)


# =============================================================================
# 4. Ecological Integrity: Rainfall is an Exogenous Climatic Forcing
# =============================================================================

def test_audit_rainfall_treated_as_exogenous_boundary_condition():
    """
    Verify that in our ecological causal modeling, climate.rainfall is NEVER
    modeled as a downstream target variable caused by land management or soil practices.
    Interventions modulate soil moisture retention (soil.moisture), not atmospheric rain.
    """
    for tpl in RELATIONSHIP_TEMPLATES:
        assert tpl.target_variable != "climate.rainfall", (
            f"Template {tpl.template_id} incorrectly models 'climate.rainfall' as a target variable. "
            "Rainfall is an exogenous climatic forcing; agricultural interventions modulate soil.moisture."
        )


# =============================================================================
# 5. Security & Gatekeeper Audit: No Recommendation Bypasses Validation
# =============================================================================

def test_audit_no_recommendation_bypasses_evidence_validation(store):
    """
    Verify that any intervention lacking evidence IDs is immediately rejected at Gate 1.
    """
    validator = EvidenceTraceabilityValidator(store=store)
    clean_state = EnvironmentalState()

    unsupported_candidate = CandidateIntervention(
        action="Install deep subsurface plastic drainage tiles",
        rationale="Drains excess moisture rapidly.",
        affected_metrics=["soil.moisture"],
        time_horizon="long",
        required_conditions=[],
        evidence_ids=[],  # Zero evidence
    )

    val_res = validator.validate_candidate(unsupported_candidate, clean_state)
    assert val_res.is_valid is False
    assert val_res.rejection_stage == "evidence"


# =============================================================================
# 6. Documentation Claims Audit: Proper Qualification of Evaluation Scores
# =============================================================================

def test_audit_no_misleading_evaluation_score_wording():
    """
    Verify that README.md and documentation explicitly qualify evaluation scores
    as internal hackathon-aligned benchmark measurements, never as 'actual judge score'.
    """
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists()
    content = readme_path.read_text(encoding="utf-8").lower()

    # Must NOT claim to be the official or actual judge score
    assert "actual judge score" not in content
    assert "official judge score" not in content

    # Must be explicitly qualified
    assert "internal hackathon" in content or "internal benchmark" in content
