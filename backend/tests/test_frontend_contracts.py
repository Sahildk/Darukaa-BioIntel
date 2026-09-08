"""Test suite verifying backend API contract compatibility with frontend TypeScript definitions."""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ClarificationResponse
from app.schemas.recommendation import RecommendationResponse


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_frontend_health_contract(client):
    """Verifies GET /api/health contract matches HealthStatus in types.ts."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["status"], str)
    assert data["readiness"] in ["ready", "degraded"]
    assert isinstance(data["version"], str)
    assert isinstance(data["service"], str)
    assert isinstance(data["components"], dict)
    for comp_name, comp_status in data["components"].items():
        assert isinstance(comp_name, str)
        assert isinstance(comp_status, str)


def test_frontend_demo_scenarios_contract(client):
    """Verifies GET /api/demo/scenarios contract matches DemoScenario in types.ts."""
    resp = client.get("/api/demo/scenarios")
    assert resp.status_code == 200
    scenarios = resp.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) >= 3

    for s in scenarios:
        assert "scenario_id" in s and isinstance(s["scenario_id"], str)
        assert "title" in s and isinstance(s["title"], str)
        assert "description" in s and isinstance(s["description"], str)
        assert "sample_request" in s and isinstance(s["sample_request"], dict)

        req = s["sample_request"]
        assert "message" in req and isinstance(req["message"], str)
        if "structured_input" in req and req["structured_input"]:
            assert isinstance(req["structured_input"], dict)


def test_frontend_recommendation_contract(client):
    """Verifies POST /api/chat recommendation payload contract matches RecommendationResponse in types.ts."""
    conv_id = f"conv-front-rec-{uuid.uuid4().hex[:8]}"
    payload = {
        "conversation_id": conv_id,
        "message": "We manage a wheat monoculture in a semi-arid zone with low rainfall and measured soil organic carbon of 0.3%.",
        "structured_input": {
            "region": "semi-arid",
            "soil_organic_carbon": 0.3,
            "rainfall": "low",
            "crop": "wheat",
            "land_use": "monoculture",
        },
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    rec_resp = RecommendationResponse.model_validate(data)
    assert rec_resp.type == "recommendation"
    assert rec_resp.conversation_id == conv_id
    assert isinstance(rec_resp.assessment, str)
    assert isinstance(rec_resp.variables_considered, list)
    assert isinstance(rec_resp.recommendations, list)
    assert len(rec_resp.recommendations) >= 1
    assert isinstance(rec_resp.limitations, list)

    # Validate RecommendationItem
    first_rec = rec_resp.recommendations[0]
    assert isinstance(first_rec.action, str)
    assert isinstance(first_rec.why, str)
    assert isinstance(first_rec.impacted_metrics, list)
    assert first_rec.time_horizon in ["short", "medium", "long"]
    assert first_rec.evidence_strength in ["Strong", "Moderate", "Limited"]
    assert isinstance(first_rec.evidence, list)
    assert len(first_rec.evidence) >= 1

    # Validate EvidenceItem
    first_ev = first_rec.evidence[0]
    assert isinstance(first_ev.evidence_id, str)
    assert isinstance(first_ev.source_id, str)
    assert isinstance(first_ev.title, str)
    assert isinstance(first_ev.publisher, str)
    assert isinstance(first_ev.excerpt, str)

    # Validate DeveloperTrace
    trace = rec_resp.developer_trace
    assert trace is not None
    assert isinstance(trace.query, str)
    assert isinstance(trace.extracted_variables, dict)
    assert isinstance(trace.retrieved_source_ids, list)
    assert isinstance(trace.reasoning_variables, list)
    assert isinstance(trace.validation_status, str)


def test_frontend_clarification_contract(client):
    """Verifies POST /api/chat clarification payload contract matches ClarificationResponse in types.ts."""
    conv_id = f"conv-front-clar-{uuid.uuid4().hex[:8]}"
    payload = {
        "conversation_id": conv_id,
        "message": "Biodiversity is declining on my land.",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    clar_resp = ClarificationResponse.model_validate(data)
    assert clar_resp.type == "clarification"
    assert clar_resp.conversation_id == conv_id
    assert isinstance(clar_resp.question, str)
    assert isinstance(clar_resp.missing_variables, list)
    assert len(clar_resp.missing_variables) >= 1


def test_frontend_state_contract(client):
    """Verifies GET /api/conversations/{id} contract matches EnvironmentalState in types.ts."""
    conv_id = f"conv-front-state-{uuid.uuid4().hex[:8]}"
    # Populate first
    client.post("/api/chat", json={
        "conversation_id": conv_id,
        "message": "We have 0.3% SOC in semi-arid cropland.",
        "structured_input": {"soil_organic_carbon": 0.3, "region": "semi-arid"},
    })

    resp = client.get(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    state = resp.json()

    # Category checks
    assert "region" in state
    assert "soil" in state
    assert "land_use" in state
    assert "biodiversity" in state
    assert "climate" in state
    assert "human_impact" in state
    assert "active_conflicts" in state

    # Field structure checks
    soc_var = state["soil"]["organic_carbon"]
    assert soc_var is not None
    assert soc_var["value"] == 0.3
    assert soc_var["source"] in ["user", "structured_input", "retrieved", "inferred"]
    assert soc_var["confidence"] in ["explicit", "estimated", "inferred"]
    assert "timestamp" in soc_var


def test_frontend_error_handling_contract(client):
    """Verifies 422 errors return parseable error details matching api.ts error handling."""
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422
    data = resp.json()
    assert "detail" in data
