"""Phase 6 tests for Conversational Intelligence, Query Parsing, and Targeted Clarification."""
import json
import pytest
from pydantic import ValidationError

from app.conversation.clarification import (
    CORE_HIGH_VALUE_VARIABLES,
    CompletenessAssessment,
    CompletenessChecker,
)
from app.conversation.flow import ConversationFlow, ConversationTurnResult
from app.conversation.parser import (
    DeterministicQueryParser,
    ExtractedObservation,
    ParsedQueryResult,
    PluggableLLMQueryParser,
)
from app.schemas.chat import ChatRequest, ClarificationResponse, StructuredInput
from app.schemas.state import (
    EnvironmentalState,
    EnvironmentalVariable,
    ProvenanceSource,
    VariableConfidence,
)
from app.state.manager import EnvironmentalStateManager


@pytest.fixture
def state_manager(tmp_path):
    """Provides an isolated SQLite-backed EnvironmentalStateManager instance."""
    db_file = tmp_path / "test_conv_state.db"
    return EnvironmentalStateManager(db_path=db_file)


@pytest.fixture
def parser():
    """Provides a DeterministicQueryParser instance."""
    return DeterministicQueryParser()


@pytest.fixture
def flow(state_manager, parser):
    """Provides an integrated ConversationFlow instance."""
    checker = CompletenessChecker(min_required_variables=3)
    return ConversationFlow(
        state_manager=state_manager,
        query_parser=parser,
        completeness_checker=checker,
    )


def test_deterministic_parser_numeric_and_categorical(parser):
    """Verify deterministic parser extracts numeric metrics and ecological conditions with exact evidence substrings."""
    query = "My farm is in a semi-arid zone growing wheat monoculture with 0.3% soil organic carbon and low rainfall."
    result = parser.parse(query)

    assert result.intent == "assessment"
    extracted_dict = {obs.variable_path: obs for obs in result.extracted_observations}

    # Verify region
    assert "region" in extracted_dict
    assert extracted_dict["region"].value == "semi-arid"
    assert "semi-arid" in extracted_dict["region"].evidence_text.lower()

    # Verify crop
    assert "land_use.crop" in extracted_dict
    assert extracted_dict["land_use.crop"].value == "wheat"
    assert "wheat" in extracted_dict["land_use.crop"].evidence_text.lower()

    # Verify land cover
    assert "land_use.land_cover" in extracted_dict
    assert extracted_dict["land_use.land_cover"].value == "monoculture"
    assert "monoculture" in extracted_dict["land_use.land_cover"].evidence_text.lower()

    # Verify soil organic carbon
    assert "soil.organic_carbon" in extracted_dict
    assert extracted_dict["soil.organic_carbon"].value == 0.3
    assert extracted_dict["soil.organic_carbon"].unit == "%"
    assert "0.3" in extracted_dict["soil.organic_carbon"].evidence_text

    # Verify rainfall
    assert "climate.rainfall" in extracted_dict
    assert extracted_dict["climate.rainfall"].value == "low"
    assert "rainfall" in extracted_dict["climate.rainfall"].evidence_text.lower()


def test_deterministic_parser_non_environmental_query(parser):
    """Verify parser does not fabricate observations or assumptions when text has no environmental metrics."""
    query = "Hello, what features do you support and how does this tool work?"
    result = parser.parse(query)

    assert len(result.extracted_observations) == 0
    assert result.intent in ["inquiry", "assessment"]


def test_parser_provenance_and_explicit_confidence(parser, state_manager):
    """Verify observations from natural language receive EXPLICIT confidence and USER provenance upon recording."""
    query = "Our soil pH is 6.5 and annual rainfall is 450 mm/year."
    result = parser.parse(query)

    for obs in result.extracted_observations:
        assert obs.confidence == VariableConfidence.EXPLICIT

    # Record to state manager
    conv_id = "conv-prov-test"
    for obs in result.extracted_observations:
        res = state_manager.add_observation(
            conversation_id=conv_id,
            variable_path=obs.variable_path,
            value=obs.value,
            unit=obs.unit,
            source=ProvenanceSource.USER,
            confidence=obs.confidence,
        )
        assert res.status == "applied"

    state = state_manager.get_state(conv_id)
    assert state.soil.ph.source == ProvenanceSource.USER
    assert state.soil.ph.confidence == VariableConfidence.EXPLICIT
    assert state.soil.ph.value == 6.5
    assert state.climate.rainfall.source == ProvenanceSource.USER
    assert state.climate.rainfall.value == 450.0
    assert state.climate.rainfall.unit == "mm/year"


def test_completeness_checker_insufficient_variables():
    """Verify completeness checker flags insufficient state (< 3 variables) and provides targeted missing variables."""
    checker = CompletenessChecker(min_required_variables=3)
    state = EnvironmentalState()
    # Provide only 1 variable
    state.biodiversity.habitat_diversity = EnvironmentalVariable(
        value="declining",
        source=ProvenanceSource.USER,
        confidence=VariableConfidence.EXPLICIT,
    )

    assessment = checker.check(state)
    assert assessment.is_complete is False
    assert len(assessment.populated_variables) == 1
    assert "biodiversity.habitat_diversity" in assessment.populated_variables

    # Must ask for targeted missing variables (at least 2 candidates to reach 3, but not all 14)
    assert 1 <= len(assessment.missing_variables) <= 3
    assert "biodiversity.habitat_diversity" not in assessment.missing_variables
    assert assessment.clarification_question is not None
    assert "?" in assessment.clarification_question


def test_completeness_checker_sufficient_variables():
    """Verify completeness checker approves state when >= 3 variables are populated without conflicts."""
    checker = CompletenessChecker(min_required_variables=3)
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)

    assessment = checker.check(state)
    assert assessment.is_complete is True
    assert len(assessment.missing_variables) == 0
    assert assessment.clarification_question is None
    assert set(assessment.populated_variables) == {"region", "soil.organic_carbon", "land_use.crop"}


def test_completeness_checker_prioritizes_conflicts():
    """Verify active unresolved conflicts take priority in clarification even if variable count >= 3."""
    checker = CompletenessChecker(min_required_variables=3)
    state = EnvironmentalState()
    state.region = EnvironmentalVariable(value="semi-arid", source=ProvenanceSource.USER)
    state.soil.organic_carbon = EnvironmentalVariable(value=0.3, unit="%", source=ProvenanceSource.USER)
    state.land_use.crop = EnvironmentalVariable(value="wheat", source=ProvenanceSource.USER)

    # Inject an active unresolved conflict
    state.active_conflicts = [
        {
            "conflict_id": "CONF-test-001",
            "variable_path": "climate.rainfall",
            "explanation": "Conflicting equal-authority observations: active value 'low' vs incoming value '600 mm/year'",
        }
    ]

    assessment = checker.check(state)
    assert assessment.is_complete is False
    assert assessment.has_conflict is True
    assert assessment.conflict_path == "climate.rainfall"
    assert "climate.rainfall" in assessment.clarification_question
    assert "conflicting" in assessment.clarification_question.lower()


def test_multi_turn_context_reuse_and_no_re_asking(flow):
    """
    Verify multi-turn flow:
    Turn 1: User supplies 2 variables -> triggers targeted clarification.
    Turn 2: User supplies 1 more variable -> system recognizes 3 total, does not re-ask Turn 1 variables, and signals ready for reasoning.
    """
    conv_id = "conv-multiturn-001"

    # Turn 1: Provide region and crop (2 variables)
    req1 = ChatRequest(
        conversation_id=conv_id,
        message="I am growing wheat in a semi-arid region. What can I do to improve land health?",
    )
    res1: ConversationTurnResult = flow.handle_turn(req1)

    assert res1.is_clarification is True
    assert res1.is_ready_for_reasoning is False
    assert res1.clarification_response is not None
    assert isinstance(res1.clarification_response, ClarificationResponse)
    assert set(res1.completeness.populated_variables) == {"region", "land_use.crop"}

    # Clarification should NOT ask for region or crop
    assert "region" not in res1.completeness.missing_variables
    assert "land_use.crop" not in res1.completeness.missing_variables
    assert "crop" not in res1.clarification_response.question.lower()

    # Turn 2: User supplies soil organic carbon
    req2 = ChatRequest(
        conversation_id=conv_id,
        message="My soil organic carbon is approximately 0.3%.",
    )
    res2: ConversationTurnResult = flow.handle_turn(req2)

    assert res2.is_clarification is False
    assert res2.is_ready_for_reasoning is True
    assert res2.clarification_response is None
    # State accumulated all 3 variables across turns
    assert "region" in res2.completeness.populated_variables
    assert "land_use.crop" in res2.completeness.populated_variables
    assert "soil.organic_carbon" in res2.completeness.populated_variables
    assert res2.environmental_state.soil.organic_carbon.value == 0.3


def test_pluggable_llm_parser_with_whitelisted_json():
    """Verify pluggable LLM parser parses valid JSON observations against the variable whitelist."""
    mock_llm_response = json.dumps({
        "intent": "recommendation_request",
        "extracted_observations": [
            {
                "variable_path": "soil.organic_carbon",
                "value": 0.4,
                "unit": "%",
                "confidence": "explicit",
                "evidence_text": "SOC is 0.4%",
            }
        ]
    })

    llm_parser = PluggableLLMQueryParser(llm_fn=lambda prompt: mock_llm_response)
    res = llm_parser.parse("SOC is 0.4%")

    assert res.intent == "recommendation_request"
    assert len(res.extracted_observations) == 1
    assert res.extracted_observations[0].variable_path == "soil.organic_carbon"
    assert res.extracted_observations[0].value == 0.4


def test_pluggable_llm_parser_rejects_hallucinated_variable_paths():
    """Verify pluggable LLM parser filters out variable paths that do not exist in VALID_VARIABLE_PATHS."""
    mock_llm_response = json.dumps({
        "intent": "assessment",
        "extracted_observations": [
            {
                "variable_path": "alien_soil.dark_matter_ratio",
                "value": 99.9,
                "confidence": "explicit",
                "evidence_text": "dark matter ratio is 99.9",
            },
            {
                "variable_path": "soil.ph",
                "value": 7.2,
                "confidence": "explicit",
                "evidence_text": "pH is 7.2",
            }
        ]
    })

    llm_parser = PluggableLLMQueryParser(llm_fn=lambda prompt: mock_llm_response)
    res = llm_parser.parse("pH is 7.2 with some strange measurements")

    # The invalid path must be filtered out
    assert len(res.extracted_observations) == 1
    assert res.extracted_observations[0].variable_path == "soil.ph"
    assert res.extracted_observations[0].value == 7.2


def test_pluggable_llm_parser_fallback_on_error():
    """Verify pluggable LLM parser falls back cleanly to deterministic parser on LLM exception or bad JSON."""
    def broken_llm(prompt: str) -> str:
        raise RuntimeError("LLM API network timeout")

    llm_parser = PluggableLLMQueryParser(llm_fn=broken_llm)
    # The fallback should extract 0.3% SOC and wheat cleanly
    res = llm_parser.parse("Growing wheat with 0.3% soil organic carbon")

    extracted_paths = [obs.variable_path for obs in res.extracted_observations]
    assert "soil.organic_carbon" in extracted_paths
    assert "land_use.crop" in extracted_paths


def test_conversation_flow_structured_and_unstructured_fusion(flow):
    """Verify conversation flow seamlessly ingests both natural text and StructuredInput with appropriate provenance."""
    conv_id = "conv-fusion-001"
    request = ChatRequest(
        conversation_id=conv_id,
        message="Soil organic carbon is 0.5% in our trial plot.",
        structured_input=StructuredInput(
            region="tropical",
            crop="rice",
        ),
    )

    result = flow.handle_turn(request)
    assert result.is_ready_for_reasoning is True
    assert result.is_clarification is False

    state = result.environmental_state
    # Text observation has USER provenance
    assert state.soil.organic_carbon.source == ProvenanceSource.USER
    assert state.soil.organic_carbon.value == 0.5

    # Structured input observations have STRUCTURED_INPUT provenance
    assert state.region.source == ProvenanceSource.STRUCTURED_INPUT
    assert state.region.value == "tropical"
    assert state.land_use.crop.source == ProvenanceSource.STRUCTURED_INPUT
    assert state.land_use.crop.value == "rice"
