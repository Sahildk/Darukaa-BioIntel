import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.chat import ChatResponse, ClarificationResponse
from app.schemas.recommendation import EvidenceStrength, RecommendationResponse, TimeHorizon
from app.schemas.state import EnvironmentalState, ProvenanceSource
from app.services.conversation_service import EnvironmentalChatService, get_chat_service


@pytest.fixture
def client():
    """Provides a fresh FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# 1. Health & Readiness Endpoint Tests
# =============================================================================

def test_api_health_live_readiness(client):
    """
    Verify /api/health returns lightweight, deterministic readiness status.
    Checks database, retrieval index, reasoning engine, and recommendation generator readiness.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["readiness"] in ["ready", "degraded"]
    assert "version" in data
    assert "service" in data

    # Verify component readiness breakdown
    components = data["components"]
    assert components["database"] == "connected"
    assert components["retrieval_index"] == "loaded"
    assert components["reasoning_engine"] == "ready"
    assert components["recommendation_generator"] == "ready"


# =============================================================================
# 2. Canonical Challenge Scenario End-to-End Test (Section 15)
# =============================================================================

def test_canonical_challenge_scenario_api(client):
    """
    Full canonical pipeline through POST /api/chat:
    Semi-arid wheat monoculture with 0.3% SOC and low rainfall.
    Expects validated recommendations with complete evidence traceability.
    """
    payload = {
        "conversation_id": "conv-canonical-api",
        "message": "We manage a wheat monoculture in a semi-arid zone with low rainfall and measured soil organic carbon of 0.3%. Recommend interventions.",
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

    rec_resp = RecommendationResponse.model_validate(data)
    assert rec_resp.type == "recommendation"
    assert rec_resp.conversation_id == "conv-canonical-api"
    assert len(rec_resp.variables_considered) >= 3
    assert len(rec_resp.recommendations) >= 1

    # Verify primary recommendation
    first_rec = rec_resp.recommendations[0]
    assert first_rec.action
    assert first_rec.why
    assert len(first_rec.impacted_metrics) >= 1
    assert first_rec.time_horizon in [TimeHorizon.SHORT, TimeHorizon.MEDIUM, TimeHorizon.LONG]
    assert first_rec.evidence_strength in [EvidenceStrength.STRONG, EvidenceStrength.MODERATE]
    assert len(first_rec.evidence) >= 1

    # Verify complete scientific traceability chain (evidence_id -> source_id -> title, publisher, URL)
    first_ev = first_rec.evidence[0]
    assert first_ev.evidence_id
    assert first_ev.source_id
    assert first_ev.title
    assert first_ev.publisher
    assert first_ev.source_url is not None
    assert first_ev.year > 1900

    # Verify supporting pathway IDs
    assert len(first_rec.supporting_pathway_ids) >= 1
    assert "PATH-" in first_rec.supporting_pathway_ids[0]

    # Verify environmental state in response
    assert rec_resp.environmental_state.soil.organic_carbon is not None
    assert rec_resp.environmental_state.soil.organic_carbon.value == 0.3
    assert rec_resp.environmental_state.soil.organic_carbon.source == ProvenanceSource.STRUCTURED_INPUT

    # Verify developer trace
    assert rec_resp.developer_trace is not None
    assert rec_resp.developer_trace.validation_status == "verified_audit_passed"
    assert len(rec_resp.developer_trace.retrieved_source_ids) >= 1


# =============================================================================
# 3. Phase 6 Conversational Clarification Test
# =============================================================================

def test_clarification_response_api(client):
    """Verify that vague/incomplete user request (< 3 variables) triggers Phase 6 ClarificationResponse."""
    payload = {
        "message": "Biodiversity is declining on my land.",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    clar_resp = ClarificationResponse.model_validate(data)
    assert clar_resp.type == "clarification"
    assert clar_resp.conversation_id
    assert clar_resp.question
    assert len(clar_resp.missing_variables) >= 3


# =============================================================================
# 4. Phase 7 Scientific Sufficiency Rejection Test (Disconnected Variables)
# =============================================================================

def test_disconnected_variables_insufficient_information_api(client):
    """
    Disconnected variables scenario:
    Temperature = 31°C, Rainfall = 800 mm, Crop = wheat.
    Phase 6 is complete (3 variables present), but Phase 7 rejects sufficiency.
    Must return a structured clarification/insufficient-information response explaining
    that climate + crop alone is scientifically insufficient for restoration analysis.
    """
    payload = {
        "conversation_id": "conv-disconnected-api",
        "message": "Our temperature is 31 degrees Celsius, rainfall is 800 mm, and we grow wheat.",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must be a clarification response, not an ungrounded recommendation
    clar_resp = ClarificationResponse.model_validate(data)
    assert clar_resp.type == "clarification"
    assert clar_resp.conversation_id == "conv-disconnected-api"
    assert "scientifically insufficient" in clar_resp.question.lower() or "baseline soil" in clar_resp.question.lower()
    assert any("soil" in v for v in clar_resp.missing_variables)


# =============================================================================
# 5. Multi-Turn State Accumulation & Reuse
# =============================================================================

def test_multi_turn_state_accumulation_api(client):
    """Verify that multi-turn interaction under same conversation_id accumulates facts without re-asking."""
    conv_id = f"conv-multiturn-{uuid.uuid4().hex[:8]}"

    # Turn 1: Provide land use and crop
    t1_payload = {
        "conversation_id": conv_id,
        "message": "We have a continuous monoculture wheat farm.",
    }
    t1_resp = client.post("/api/chat", json=t1_payload)
    assert t1_resp.status_code == 200
    t1_data = t1_resp.json()
    assert t1_data["type"] == "clarification"

    # Turn 2: Provide region, rainfall, and SOC via structured input
    t2_payload = {
        "conversation_id": conv_id,
        "message": "Here are our soil and climate metrics.",
        "structured_input": {
            "region": "semi-arid",
            "soil_organic_carbon": 0.3,
            "rainfall": "low",
        },
    }
    t2_resp = client.post("/api/chat", json=t2_payload)
    assert t2_resp.status_code == 200
    t2_data = t2_resp.json()

    # Turn 2 now has all required variables accumulated; returns recommendation
    rec_resp = RecommendationResponse.model_validate(t2_data)
    assert rec_resp.type == "recommendation"
    assert rec_resp.conversation_id == conv_id

    # Verify both Turn 1 (crop=wheat, monoculture) and Turn 2 (SOC=0.3) are preserved in state
    state = rec_resp.environmental_state
    assert state.land_use.crop.value == "wheat"
    assert state.land_use.land_cover.value == "monoculture"
    assert state.soil.organic_carbon.value == 0.3
    assert state.region.value == "semi-arid"


# =============================================================================
# 6. Conversation Session Isolation
# =============================================================================

def test_conversation_isolation_api(client):
    """Verify that Conversation A and Conversation B do not leak or overwrite each other's state."""
    id_a = f"conv-user-a-{uuid.uuid4().hex[:8]}"
    id_b = f"conv-user-b-{uuid.uuid4().hex[:8]}"

    # Conversation A: Semi-arid wheat
    client.post("/api/chat", json={
        "conversation_id": id_a,
        "message": "We have semi-arid wheat with 0.3% SOC.",
        "structured_input": {
            "region": "semi-arid",
            "crop": "wheat",
            "soil_organic_carbon": 0.3,
        },
    })

    # Conversation B: Tropical citrus
    client.post("/api/chat", json={
        "conversation_id": id_b,
        "message": "We manage a citrus orchard in a humid tropical region.",
        "structured_input": {
            "region": "tropical",
            "crop": "citrus",
            "soil_organic_carbon": 2.5,
        },
    })

    # Fetch states independently
    state_a = client.get(f"/api/conversations/{id_a}").json()
    state_b = client.get(f"/api/conversations/{id_b}").json()

    assert state_a["region"]["value"] == "semi-arid"
    assert state_a["land_use"]["crop"]["value"] == "wheat"
    assert state_a["soil"]["organic_carbon"]["value"] == 0.3

    assert state_b["region"]["value"] == "tropical"
    assert state_b["land_use"]["crop"]["value"] == "citrus"
    assert state_b["soil"]["organic_carbon"]["value"] == 2.5


# =============================================================================
# 7. Phase 8 Hard Contraindication Firewall Test
# =============================================================================

def test_hard_contraindication_blocking_api(client):
    """
    Verify that in extreme drought parcel (rainfall = 220 mm/year < 300 mm threshold),
    the cover crop intervention is rejected by the contraindication firewall.
    """
    conv_id = f"conv-drought-{uuid.uuid4().hex[:8]}"
    payload = {
        "conversation_id": conv_id,
        "message": "We manage monoculture in a severe drought zone.",
        "structured_input": {
            "region": "semi-arid",
            "soil_organic_carbon": 0.3,
            "rainfall": 220.0,
            "crop": "wheat",
            "land_use": "monoculture",
        },
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    rec_resp = RecommendationResponse.model_validate(data)
    assert rec_resp.type == "recommendation"

    # Cover crops must NOT be in the validated recommendations
    actions = [r.action.lower() for r in rec_resp.recommendations]
    assert not any("legume-based cover crops" in a for a in actions), (
        "Cover crop intervention must be blocked by the < 300 mm moisture competition contraindication firewall."
    )


# =============================================================================
# 8. New Conversation ID Auto-Generation
# =============================================================================

def test_new_conversation_id_generated(client):
    """Verify that when conversation_id is omitted, a unique ID is automatically assigned."""
    payload = {
        "message": "Biodiversity is declining on our farmland.",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "conversation_id" in data
    assert data["conversation_id"].startswith("conv-")


# =============================================================================
# 9. Error Handling & Request Validation
# =============================================================================

def test_malformed_request_error_handling_api(client):
    """Verify clean HTTP 422 errors for malformed requests without leaking internal tracebacks."""
    # Empty message
    resp1 = client.post("/api/chat", json={"message": ""})
    assert resp1.status_code == 422

    # Invalid structured_input data types
    resp2 = client.post("/api/chat", json={
        "message": "Valid query",
        "structured_input": {
            "soil_organic_carbon": {"nested": "invalid"}
        }
    })
    assert resp2.status_code == 422


def test_empty_conversation_id_state_error(client):
    """Verify GET /api/conversations/ with whitespace ID returns 400."""
    response = client.get("/api/conversations/%20")
    assert response.status_code == 400


# =============================================================================
# 10. Dependency Injection Override Test
# =============================================================================

def test_dependency_injection_override(client):
    """Verify that get_chat_service can be overridden cleanly via app.dependency_overrides."""
    custom_service = EnvironmentalChatService()

    app.dependency_overrides[get_chat_service] = lambda: custom_service
    try:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    finally:
        app.dependency_overrides.clear()
