"""Conversation flow manager coordinating query understanding, state management, and completeness checking."""
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

from app.conversation.clarification import CompletenessAssessment, CompletenessChecker
from app.conversation.parser import BaseQueryParser, DeterministicQueryParser, ParsedQueryResult
from app.schemas.chat import ChatRequest, ClarificationResponse
from app.schemas.state import EnvironmentalState, ProvenanceSource
from app.state.manager import EnvironmentalStateManager, UpdateResult


class ConversationTurnResult(BaseModel):
    """Result of processing a conversational turn through query parsing, state tracking, and completeness checking."""
    conversation_id: str
    is_clarification: bool
    is_ready_for_reasoning: bool
    parsed_query: ParsedQueryResult
    update_results: List[UpdateResult] = Field(default_factory=list)
    completeness: CompletenessAssessment
    clarification_response: Optional[ClarificationResponse] = None
    environmental_state: EnvironmentalState


class ConversationFlow:
    """
    Coordinates the conversational understanding pipeline:
    1. Interprets natural-language text via query parser
    2. Ingests extracted facts into the EnvironmentalStateManager with strict provenance
    3. Merges optional structured input
    4. Evaluates multi-metric completeness and unresolved conflicts
    5. Returns either a targeted ClarificationResponse or signals readiness for reasoning
    """

    def __init__(
        self,
        state_manager: Optional[EnvironmentalStateManager] = None,
        query_parser: Optional[BaseQueryParser] = None,
        completeness_checker: Optional[CompletenessChecker] = None,
    ):
        self.state_manager = state_manager or EnvironmentalStateManager()
        self.query_parser = query_parser or DeterministicQueryParser()
        self.completeness_checker = completeness_checker or CompletenessChecker()

    def handle_turn(self, request: ChatRequest) -> ConversationTurnResult:
        """
        Processes a single chat turn.
        Never guesses missing data or fabricates assumptions.
        Preserves established facts across turns.
        """
        # 1. Resolve or assign conversation ID
        conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:8]}"

        # 2. Parse natural language query
        parsed = self.query_parser.parse(request.message)

        # 3. Ingest extracted observations with USER provenance
        update_results: List[UpdateResult] = []
        for obs in parsed.extracted_observations:
            res = self.state_manager.add_observation(
                conversation_id=conversation_id,
                variable_path=obs.variable_path,
                value=obs.value,
                unit=obs.unit,
                source=ProvenanceSource.USER,
                confidence=obs.confidence,
            )
            update_results.append(res)

        # 4. Ingest structured input if provided with STRUCTURED_INPUT provenance
        if request.structured_input:
            struct_results = self.state_manager.update_from_structured_input(
                conversation_id=conversation_id,
                structured_input=request.structured_input,
            )
            update_results.extend(struct_results)

        # 5. Fetch current consolidated environmental state
        current_state = self.state_manager.get_state(conversation_id)

        # 6. Evaluate state completeness
        assessment = self.completeness_checker.check(current_state)

        # 7. Formulate turn outcome
        if not assessment.is_complete:
            clarification_resp = ClarificationResponse(
                type="clarification",
                conversation_id=conversation_id,
                question=assessment.clarification_question or "Could you provide additional details on your land conditions?",
                missing_variables=assessment.missing_variables,
                environmental_state=current_state,
            )
            return ConversationTurnResult(
                conversation_id=conversation_id,
                is_clarification=True,
                is_ready_for_reasoning=False,
                parsed_query=parsed,
                update_results=update_results,
                completeness=assessment,
                clarification_response=clarification_resp,
                environmental_state=current_state,
            )

        return ConversationTurnResult(
            conversation_id=conversation_id,
            is_clarification=False,
            is_ready_for_reasoning=True,
            parsed_query=parsed,
            update_results=update_results,
            completeness=assessment,
            clarification_response=None,
            environmental_state=current_state,
        )
