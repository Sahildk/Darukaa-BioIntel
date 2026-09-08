"""Phase 1 contract verification tests.

Verifies schema compliance, validation rules, 422 error rejections,
provenance tracking, and deterministic contract endpoints without
invoking any external LLM, vector DB, or network service.
"""
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.schemas.chat import (
    ChatRequest,
    ClarificationResponse,
    StructuredInput,
)
from app.schemas.demo import DemoScenario, EvaluationReport
from app.schemas.evidence import CandidateIntervention, EvidenceItem
from app.schemas.recommendation import (
    DeveloperTrace,
    EvidenceStrength,
    RecommendationItem,
    RecommendationResponse,
    TimeHorizon,
)
from app.schemas.state import (
    EnvironmentalState,
    EnvironmentalVariable,
    ProvenanceSource,
    SoilState,
    VariableConfidence,
)


# ===========================================================================
# 1. Schema Unit & Validation Tests
# ===========================================================================

def test_environmental_variable_provenance():
    """Verify EnvironmentalVariable enforces primitive typing, provenance, and UTC timestamp."""
    var = EnvironmentalVariable(
        value=0.3,
        unit="%",
        source=ProvenanceSource.STRUCTURED_INPUT,
        confidence=VariableConfidence.EXPLICIT,
    )
    assert var.value == 0.3
    assert var.unit == "%"
    assert var.source == ProvenanceSource.STRUCTURED_INPUT
    assert var.confidence == VariableConfidence.EXPLICIT
    
    # Verify timestamp is timezone-aware ISO format
    dt = datetime.fromisoformat(var.timestamp)
    assert dt.tzinfo is not None

    # Verify string, int, and bool values are accepted
    assert EnvironmentalVariable(value="low").value == "low"
    assert EnvironmentalVariable(value=42).value == 42
    assert EnvironmentalVariable(value=True).value is True

    # Verify arbitrary objects/lists/dicts are rejected as values
    with pytest.raises(ValidationError):
        EnvironmentalVariable(value={"nested": "dict"})

    with pytest.raises(ValidationError):
        EnvironmentalVariable(value=[1, 2, 3])


def test_evidence_item_fields():
    """Verify EvidenceItem correctly stores source_url, doi, and publisher metadata."""
    item = EvidenceItem(
        evidence_id="EVD-TEST-001",
        source_id="SRC-FAO-2020",
        title="Recarbonizing Global Soils",
        publisher="Food and Agriculture Organization (FAO)",
        year=2020,
        excerpt="Legume cover crops improve soil organic carbon by 15-25%.",
        source_url="https://www.fao.org/documents/card/en/c/ca9668en",
        doi="10.4060/ca9668en",
        relevance_score=0.95,
    )
    assert item.evidence_id == "EVD-TEST-001"
    assert item.source_url == "https://www.fao.org/documents/card/en/c/ca9668en"
    assert item.doi == "10.4060/ca9668en"
    assert item.year == 2020


def test_candidate_intervention_contraindications():
    """Verify CandidateIntervention requires contraindications field."""
    intervention = CandidateIntervention(
        action="Plant fast-growing eucalyptus buffer",
        rationale="Creates rapid biomass and wind barrier",
        affected_metrics=["biomass", "wind_erosion"],
        time_horizon="medium",
        required_conditions=["adequate groundwater"],
        evidence_ids=["EVD-001"],
        contraindications=["arid zones with water table depletion risk"],
    )
    assert len(intervention.contraindications) == 1
    assert "arid zones" in intervention.contraindications[0]


def test_recommendation_item_evidence_strength():
    """Verify RecommendationItem validates strict EvidenceStrength enum."""
    evidence = EvidenceItem(
        evidence_id="EVD-001",
        source_id="SRC-001",
        title="Study Title",
        publisher="Publisher",
        excerpt="Excerpt content",
    )
    rec = RecommendationItem(
        action="Implement intercropping",
        why="Diversifies soil microbial fauna",
        impacted_metrics=["biodiversity", "soil_organic_carbon"],
        time_horizon=TimeHorizon.MEDIUM,
        evidence_strength=EvidenceStrength.STRONG,
        evidence=[evidence],
    )
    assert rec.evidence_strength == EvidenceStrength.STRONG
    assert rec.time_horizon == TimeHorizon.MEDIUM

    # Invalid evidence strength should raise ValidationError
    with pytest.raises(ValidationError):
        RecommendationItem(
            action="Action",
            why="Why",
            impacted_metrics=["metric"],
            time_horizon=TimeHorizon.SHORT,
            evidence_strength="ArbitraryConfidenceScore",  # type: ignore
            evidence=[evidence],
        )


# ===========================================================================
# 2. API Contract Endpoint Tests (TestClient)
# ===========================================================================

def test_health_check(client):
    """Verify system health endpoint returns contract mock status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "contract_mock"
    assert "version" in data


def test_chat_endpoint_recommendation_flow(client):
    """Verify POST /api/chat returns a valid RecommendationResponse for complete queries."""
    payload = {
        "message": "We have 0.3% soil organic carbon in a semi-arid wheat monoculture under low rainfall. Recommend interventions.",
        "structured_input": {
            "region": "semi-arid",
            "soil_organic_carbon": 0.3,
            "rainfall": "low",
            "crop": "wheat",
            "land_use": "monoculture",
        },
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Validate against RecommendationResponse Pydantic schema
    rec_resp = RecommendationResponse.model_validate(data)
    assert rec_resp.type == "recommendation"
    assert len(rec_resp.variables_considered) >= 3
    assert len(rec_resp.recommendations) > 0

    # Validate recommendation item structure
    first_rec = rec_resp.recommendations[0]
    assert first_rec.action
    assert first_rec.why
    assert len(first_rec.impacted_metrics) > 0
    assert first_rec.time_horizon in [TimeHorizon.SHORT, TimeHorizon.MEDIUM, TimeHorizon.LONG]
    assert first_rec.evidence_strength in [EvidenceStrength.STRONG, EvidenceStrength.MODERATE, EvidenceStrength.LIMITED]
    assert len(first_rec.evidence) > 0
    assert first_rec.evidence[0].source_url is not None

    # Validate environmental state in response
    assert rec_resp.environmental_state.soil.organic_carbon is not None
    assert rec_resp.environmental_state.soil.organic_carbon.value == 0.3
    assert rec_resp.environmental_state.soil.organic_carbon.source == ProvenanceSource.STRUCTURED_INPUT

    # Validate developer trace
    assert rec_resp.developer_trace is not None
    assert rec_resp.developer_trace.validation_status == "verified_audit_passed"


def test_chat_endpoint_clarification_flow(client):
    """Verify POST /api/chat returns a ClarificationResponse when critical variables are missing."""
    payload = {
        "message": "Biodiversity is declining on my land.",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Validate against ClarificationResponse Pydantic schema
    clar_resp = ClarificationResponse.model_validate(data)
    assert clar_resp.type == "clarification"
    assert clar_resp.question
    assert len(clar_resp.missing_variables) >= 3
    assert "soil_organic_carbon" in clar_resp.missing_variables


def test_chat_endpoint_rejection_of_invalid_requests(client):
    """Verify POST /api/chat returns 422 Unprocessable Entity for schema violations."""
    # 1. Empty message
    resp1 = client.post("/api/chat", json={"message": ""})
    assert resp1.status_code == 422

    # 2. Missing message field
    resp2 = client.post("/api/chat", json={"conversation_id": "abc"})
    assert resp2.status_code == 422

    # 3. Invalid structured_input data types (e.g. nested dictionary where float/str expected)
    resp3 = client.post("/api/chat", json={
        "message": "Valid query",
        "structured_input": {
            "soil_organic_carbon": {"invalid": "object"}
        }
    })
    assert resp3.status_code == 422


def test_conversation_state_endpoint(client):
    """Verify GET /api/conversations/{id} returns EnvironmentalState."""
    # First populate state via /api/chat with structured input
    client.post(
        "/api/chat",
        json={
            "conversation_id": "conv-123",
            "message": "We have 0.3% SOC in our cropland.",
            "structured_input": {"soil_organic_carbon": 0.3},
        },
    )
    response = client.get("/api/conversations/conv-123")
    assert response.status_code == 200
    state = EnvironmentalState.model_validate(response.json())
    assert state.soil.organic_carbon is not None
    assert state.soil.organic_carbon.value == 0.3


def test_demo_scenarios_endpoint(client):
    """Verify GET /api/demo/scenarios returns the 3 evaluator scenarios."""
    response = client.get("/api/demo/scenarios")
    assert response.status_code == 200
    scenarios = [DemoScenario.model_validate(item) for item in response.json()]
    assert len(scenarios) == 3

    scenario_ids = [s.scenario_id for s in scenarios]
    assert "SCENARIO-001" in scenario_ids
    assert "SCENARIO-002" in scenario_ids
    assert "SCENARIO-003" in scenario_ids

    # Verify each scenario has valid sample_request
    for s in scenarios:
        assert s.sample_request.message


def test_evaluate_run_stub_endpoint(client):
    """Verify POST /api/evaluate/run returns formatted EvaluationReport for T-001 to T-009."""
    response = client.post("/api/evaluate/run")
    assert response.status_code == 200
    report = EvaluationReport.model_validate(response.json())
    assert report.total_tests == 9
    assert report.passed_tests == 9
    test_ids = [r.test_id for r in report.results]
    for i in range(1, 10):
        assert f"T-00{i}" in test_ids
