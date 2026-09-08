"""Phase 5 tests for EnvironmentalStateManager, multi-turn memory, provenance, and conflict resolution."""
import pytest
from pydantic import ValidationError

from app.schemas.chat import StructuredInput
from app.schemas.state import (
    EnvironmentalState,
    EnvironmentalVariable,
    ProvenanceSource,
    VariableConfidence,
)
from app.state.manager import EnvironmentalStateManager
from app.state.models import AuthorityLevel, ConflictRecord, get_authority_level


@pytest.fixture
def state_manager(tmp_path):
    """Provides an isolated SQLite-backed EnvironmentalStateManager instance."""
    db_file = tmp_path / "test_state.db"
    return EnvironmentalStateManager(db_path=db_file)


def test_first_turn_state_creation(state_manager):
    """Verify first-turn state initializes empty categories and applies first observation."""
    conv_id = "conv-first-turn"
    state = state_manager.get_state(conv_id)
    assert state.soil.organic_carbon is None
    assert state.climate.rainfall is None

    res = state_manager.record_observation(
        conversation_id=conv_id,
        variable_path="soil.organic_carbon",
        value=0.3,
        unit="%",
        source=ProvenanceSource.USER,
        confidence=VariableConfidence.EXPLICIT,
    )
    assert res.status == "applied"
    assert res.observation_id.startswith(f"OBS-{conv_id[:6]}")

    updated_state = state_manager.get_state(conv_id)
    assert updated_state.soil.organic_carbon is not None
    assert updated_state.soil.organic_carbon.value == 0.3
    assert updated_state.soil.organic_carbon.unit == "%"
    assert updated_state.soil.organic_carbon.source == ProvenanceSource.USER


def test_multi_turn_state_accumulation(state_manager):
    """Verify variables accumulate across turns without regressing earlier state."""
    conv_id = "conv-multi-turn"

    # Turn 1: User provides region and rainfall
    state_manager.record_observation(
        conversation_id=conv_id,
        variable_path="region",
        value="semi-arid",
        source=ProvenanceSource.USER,
    )
    state_manager.record_observation(
        conversation_id=conv_id,
        variable_path="climate.rainfall",
        value="low",
        source=ProvenanceSource.USER,
    )

    # Turn 2: User provides crop and soil carbon
    state_manager.record_observation(
        conversation_id=conv_id,
        variable_path="land_use.crop",
        value="wheat",
        source=ProvenanceSource.USER,
    )
    state_manager.record_observation(
        conversation_id=conv_id,
        variable_path="soil.organic_carbon",
        value=0.3,
        unit="%",
        source=ProvenanceSource.USER,
    )

    final_state = state_manager.get_state(conv_id)
    # Turn 1 variables preserved
    assert final_state.region.value == "semi-arid"
    assert final_state.climate.rainfall.value == "low"
    # Turn 2 variables present
    assert final_state.land_use.crop.value == "wheat"
    assert final_state.soil.organic_carbon.value == 0.3


def test_partial_state_updates_isolation(state_manager):
    """Verify updating a single variable does not touch or clear unrelated variables."""
    conv_id = "conv-partial"
    state_manager.record_observation(conv_id, "climate.rainfall", "low")
    state_manager.record_observation(conv_id, "land_use.crop", "wheat")
    state_manager.record_observation(conv_id, "soil.ph", 6.5)

    # Partial update to soil.ph
    state_manager.record_observation(conv_id, "soil.ph", 6.5)  # Re-affirm

    state = state_manager.get_state(conv_id)
    assert state.climate.rainfall.value == "low"
    assert state.land_use.crop.value == "wheat"
    assert state.soil.ph.value == 6.5


def test_provenance_and_authority_separation(state_manager):
    """Verify user and structured_input both have USER_DIRECT authority level."""
    assert get_authority_level(ProvenanceSource.USER) == AuthorityLevel.USER_DIRECT
    assert get_authority_level(ProvenanceSource.STRUCTURED_INPUT) == AuthorityLevel.USER_DIRECT
    assert get_authority_level(ProvenanceSource.RETRIEVED) == AuthorityLevel.EXTERNAL
    assert get_authority_level(ProvenanceSource.INFERRED) == AuthorityLevel.INFERRED


def test_inferred_cannot_overwrite_explicit_user_fact(state_manager):
    """Verify lower-authority INFERRED observation is rejected when a USER fact exists."""
    conv_id = "conv-inferred-reject"

    # User establishes SOC = 0.3%
    state_manager.record_observation(
        conv_id,
        "soil.organic_carbon",
        value=0.3,
        source=ProvenanceSource.USER,
        confidence=VariableConfidence.EXPLICIT,
    )

    # Inferred observation attempts to overwrite with 0.8%
    res = state_manager.record_observation(
        conv_id,
        "soil.organic_carbon",
        value=0.8,
        source=ProvenanceSource.INFERRED,
        confidence=VariableConfidence.INFERRED,
    )

    assert res.status == "rejected_precedence"
    state = state_manager.get_state(conv_id)
    # User fact must remain 0.3%
    assert state.soil.organic_carbon.value == 0.3
    assert state.soil.organic_carbon.source == ProvenanceSource.USER

    # But inferred observation is recorded in immutable history
    history = state_manager.get_observation_history(conv_id, "soil.organic_carbon")
    assert len(history) == 2
    assert history[0].value == 0.3
    assert history[1].value == 0.8
    assert history[1].source == ProvenanceSource.INFERRED


def test_user_fact_overwrites_prior_inferred_estimate(state_manager):
    """Verify higher-authority USER observation successfully replaces an earlier INFERRED estimate."""
    conv_id = "conv-user-override"

    # System had inferred rainfall = "moderate"
    state_manager.record_observation(
        conv_id,
        "climate.rainfall",
        value="moderate",
        source=ProvenanceSource.INFERRED,
        confidence=VariableConfidence.ESTIMATED,
    )
    assert state_manager.get_state(conv_id).climate.rainfall.value == "moderate"

    # User explicitly states rainfall = "low" (<300mm)
    res = state_manager.record_observation(
        conv_id,
        "climate.rainfall",
        value="low",
        source=ProvenanceSource.USER,
        confidence=VariableConfidence.EXPLICIT,
    )
    assert res.status == "applied"
    state = state_manager.get_state(conv_id)
    assert state.climate.rainfall.value == "low"
    assert state.climate.rainfall.source == ProvenanceSource.USER


def test_conflicting_observations_detection(state_manager):
    """Verify conflicting observations of equal authority create an explicit ConflictRecord."""
    conv_id = "conv-conflict"

    # Observation 1: User says rainfall is low
    res1 = state_manager.record_observation(
        conv_id,
        "climate.rainfall",
        value="low",
        source=ProvenanceSource.USER,
    )
    assert res1.status == "applied"

    # Observation 2: Structured input later claims rainfall is 950 (high)
    res2 = state_manager.record_observation(
        conv_id,
        "climate.rainfall",
        value=950,
        unit="mm/year",
        source=ProvenanceSource.STRUCTURED_INPUT,
    )
    assert res2.status == "conflict_detected"
    assert res2.conflict is not None
    assert res2.conflict.status == "unresolved"

    # Verify conflict appears in active conflicts
    conflicts = state_manager.list_active_conflicts(conv_id)
    assert len(conflicts) == 1
    conf = conflicts[0]
    assert conf.variable_path == "climate.rainfall"
    assert conf.existing_observation_id == res1.observation_id
    assert conf.incoming_observation_id == res2.observation_id

    # Active value remains the existing one pending resolution
    state = state_manager.get_state(conv_id)
    assert state.climate.rainfall.value == "low"
    assert len(state.active_conflicts) == 1


def test_conflict_resolution_by_existing_observation_id(state_manager):
    """Verify resolve_conflict() requires selecting an existing observation_id."""
    conv_id = "conv-resolve"

    res1 = state_manager.record_observation(conv_id, "soil.ph", 6.0, source=ProvenanceSource.USER)
    res2 = state_manager.record_observation(conv_id, "soil.ph", 7.5, source=ProvenanceSource.STRUCTURED_INPUT)
    assert res2.status == "conflict_detected"
    conf_id = res2.conflict.conflict_id

    # Selecting the second observation ID (7.5) resolves the conflict
    resolved_state = state_manager.resolve_conflict(conv_id, conf_id, res2.observation_id)
    assert resolved_state.soil.ph.value == 7.5
    assert resolved_state.soil.ph.observation_id == res2.observation_id

    # Active conflicts list is now empty
    assert len(state_manager.list_active_conflicts(conv_id)) == 0

    # Attempting to resolve with an arbitrary or non-existent ID raises ValueError
    with pytest.raises(ValueError):
        state_manager.resolve_conflict(conv_id, conf_id, "OBS-NONEXISTENT-999")


def test_conversation_session_isolation(state_manager):
    """Verify state updates in conversation A never leak into conversation B."""
    conv_a = "conv-alpha-001"
    conv_b = "conv-beta-002"

    state_manager.record_observation(conv_a, "land_use.crop", "wheat", source=ProvenanceSource.USER)
    state_manager.record_observation(conv_b, "land_use.crop", "rice", source=ProvenanceSource.USER)

    state_a = state_manager.get_state(conv_a)
    state_b = state_manager.get_state(conv_b)

    assert state_a.land_use.crop.value == "wheat"
    assert state_b.land_use.crop.value == "rice"


def test_update_from_structured_input(state_manager):
    """Verify StructuredInput batch updates state variables with STRUCTURED_INPUT provenance."""
    conv_id = "conv-structured-batch"

    payload = StructuredInput(
        region="semi-arid",
        soil_organic_carbon=0.3,
        soil_ph=6.8,
        rainfall="low",
        crop="wheat",
        land_use="monoculture",
    )

    results = state_manager.update_from_structured_input(conv_id, payload)
    assert len(results) == 6
    for r in results:
        assert r.status == "applied"

    state = state_manager.get_state(conv_id)
    assert state.region.value == "semi-arid"
    assert state.soil.organic_carbon.value == 0.3
    assert state.soil.organic_carbon.unit == "%"
    assert state.soil.ph.value == 6.8
    assert state.climate.rainfall.value == "low"
    assert state.land_use.crop.value == "wheat"
    assert state.land_use.land_cover.value == "monoculture"
    assert state.soil.organic_carbon.source == ProvenanceSource.STRUCTURED_INPUT


def test_serialization_deserialization_fidelity(state_manager):
    """Verify EnvironmentalState round-trips through JSON serialization without data loss."""
    conv_id = "conv-roundtrip"
    state_manager.record_observation(conv_id, "soil.organic_carbon", 0.3, "%", ProvenanceSource.STRUCTURED_INPUT)
    state_manager.record_observation(conv_id, "climate.rainfall", "low", None, ProvenanceSource.USER)

    original_state = state_manager.get_state(conv_id)
    json_str = original_state.model_dump_json()

    rehydrated = EnvironmentalState.model_validate_json(json_str)
    assert rehydrated.soil.organic_carbon.value == original_state.soil.organic_carbon.value
    assert rehydrated.soil.organic_carbon.unit == original_state.soil.organic_carbon.unit
    assert rehydrated.soil.organic_carbon.source == original_state.soil.organic_carbon.source
    assert rehydrated.climate.rainfall.value == original_state.climate.rainfall.value
