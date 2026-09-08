"""Application service orchestrating conversation, state, reasoning, and recommendation subsystems."""
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import Request

from app.config import settings
from app.conversation.flow import ConversationFlow, ConversationTurnResult
from app.knowledge.indexer import InvertedIndex
from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.reasoning.engine import EcologicalReasoningEngine
from app.reasoning.models import ReasoningResult
from app.recommendation.generator import RecommendationGenerator
from app.recommendation.models import RecommendationResult
from app.retrieval.hybrid import HybridRetriever
from app.schemas.chat import ChatRequest, ChatResponse, ClarificationResponse
from app.schemas.recommendation import DeveloperTrace, RecommendationResponse
from app.schemas.state import EnvironmentalState
from app.state.manager import EnvironmentalStateManager


class EnvironmentalChatService:
    """
    Application-scoped orchestration service coordinating:
    1. Phase 6 ConversationFlow (natural language parsing, observation extraction, completeness check)
    2. Phase 5 EnvironmentalStateManager (provenance preservation, session-isolated state)
    3. Phase 7 EcologicalReasoningEngine (scientific sufficiency gate, multi-metric causal pathways)
    4. Phase 8 RecommendationGenerator & EvidenceTraceabilityValidator (evidence resolution, quantitative firewall, contraindications)
    """

    def __init__(
        self,
        flow: Optional[ConversationFlow] = None,
        reasoning_engine: Optional[EcologicalReasoningEngine] = None,
        recommendation_generator: Optional[RecommendationGenerator] = None,
        state_manager: Optional[EnvironmentalStateManager] = None,
        knowledge_store: Optional[KnowledgeStore] = None,
        index: Optional[InvertedIndex] = None,
    ):
        self.knowledge_store = knowledge_store or KnowledgeStore(db_path=REPO_ROOT / "data/knowledge.db")
        self.index = index or InvertedIndex.load_from_file(REPO_ROOT / "data/lexical_index.json")
        self.state_manager = state_manager or EnvironmentalStateManager(db_path=REPO_ROOT / "data/state.db")

        self.retriever = HybridRetriever(self.knowledge_store, self.index)
        self.flow = flow or ConversationFlow(state_manager=self.state_manager)
        self.reasoning_engine = reasoning_engine or EcologicalReasoningEngine(retriever=self.retriever)
        self.recommendation_generator = recommendation_generator or RecommendationGenerator(store=self.knowledge_store)

    def process_chat(self, request: ChatRequest) -> ChatResponse:
        """
        Processes a conversational turn through the strict multi-phase pipeline:
        1. Conversation Flow & State Ingestion (Phase 5 & 6)
        2. Phase 6 Completeness & Conflict Check
        3. Phase 7 Scientific Sufficiency Check
        4. Phase 7 Multi-Metric Reasoning & Sequential Pathways
        5. Phase 8 Candidate Validation & Recommendation Generation
        """
        # Step 1: Conversation Flow (Phase 5 state update + Phase 6 query understanding)
        turn_result: ConversationTurnResult = self.flow.handle_turn(request)
        conv_id = turn_result.conversation_id
        state = turn_result.environmental_state

        # Step 2: Phase 6 Conversational Completeness / Conflict Check
        # If variables are missing (< 3) or there is an unresolved conflicting observation
        if turn_result.is_clarification:
            clar = turn_result.clarification_response
            formatted_missing = []
            for v in clar.missing_variables:
                formatted_missing.append(v)
                if "." in v:
                    formatted_missing.append(v.replace(".", "_"))
            clar.missing_variables = list(dict.fromkeys(formatted_missing))
            return clar

        # Step 3: Phase 7 Multi-Metric Ecological Reasoning Gate
        reasoning_res: ReasoningResult = self.reasoning_engine.reason(conv_id, state)
        sufficiency = reasoning_res.scientific_sufficiency

        # If Phase 7 determines the input is scientifically insufficient
        # (e.g. disconnected variables: temperature + rainfall + crop without baseline soil condition or land management)
        if not sufficiency.is_scientifically_sufficient:
            # Formulate targeted scientific diagnostic question
            diagnostic_question = (
                sufficiency.missing_critical_context[0]
                if sufficiency.missing_critical_context
                else "Baseline soil condition (e.g., SOC % or pH) or land management practice is required for ecological analysis."
            )
            return ClarificationResponse(
                type="clarification",
                conversation_id=conv_id,
                question=diagnostic_question,
                missing_variables=[
                    "soil.organic_carbon",
                    "soil_organic_carbon",
                    "land_use.land_cover",
                    "land_use_land_cover",
                ],
                environmental_state=state,
            )

        # Step 4: Phase 8 Recommendation Generation & Evidence Validation
        rec_res: RecommendationResult = self.recommendation_generator.generate(conv_id, reasoning_res, state)

        # Build DeveloperTrace
        dev_trace = DeveloperTrace(
            query=request.message,
            extracted_variables={v.path: v.value for v in reasoning_res.variables_considered},
            retrieval_query=None,
            retrieved_source_ids=sorted(list({c.source_id for c in reasoning_res.retrieved_chunks})),
            reasoning_variables=[v.path for v in reasoning_res.variables_considered],
            validation_status="verified_audit_passed" if rec_res.evidence_validation_passed else "validation_failed",
        )

        # Step 5: Format RecommendationResponse
        assessment = (
            f"Multi-metric ecological assessment for {conv_id} across {len(reasoning_res.variables_considered)} variables. "
            f"Identified {len(reasoning_res.active_pathways)} causal pathway(s) and substantiated {len(rec_res.recommendations)} validated recommendation(s)."
        )

        all_limitations = list(rec_res.limitations)
        if not rec_res.recommendations:
            all_limitations.append("No candidate intervention satisfied evidence and contraindication validation criteria.")

        return RecommendationResponse(
            type="recommendation",
            conversation_id=conv_id,
            assessment=assessment,
            variables_considered=[v.path for v in reasoning_res.variables_considered],
            recommendations=rec_res.recommendations,
            environmental_state=state,
            limitations=all_limitations,
            developer_trace=dev_trace,
        )

    def get_health_status(self) -> Dict[str, Any]:
        """
        Lightweight, deterministic readiness and liveness check.
        Inspects queryability of KnowledgeStore and index availability without re-indexing.
        """
        components: Dict[str, str] = {}
        is_ready = True

        # 1. Database check
        try:
            sources = self.knowledge_store.list_sources()
            if len(sources) > 0:
                components["database"] = "connected"
            else:
                components["database"] = "empty"
                is_ready = False
        except Exception:
            components["database"] = "unavailable"
            is_ready = False

        # 2. Retrieval index check
        try:
            if hasattr(self.index, "doc_lengths") and len(self.index.doc_lengths) > 0:
                components["retrieval_index"] = "loaded"
            else:
                components["retrieval_index"] = "empty"
                is_ready = False
        except Exception:
            components["retrieval_index"] = "unavailable"
            is_ready = False

        # 3. Reasoning engine check
        if hasattr(self.reasoning_engine, "templates") and len(self.reasoning_engine.templates) > 0:
            components["reasoning_engine"] = "ready"
        else:
            components["reasoning_engine"] = "uninitialized"
            is_ready = False

        # 4. Recommendation generator check
        if hasattr(self.recommendation_generator, "validator") and self.recommendation_generator.validator is not None:
            components["recommendation_generator"] = "ready"
        else:
            components["recommendation_generator"] = "uninitialized"
            is_ready = False

        return {
            "status": "ok",
            "readiness": "ready" if is_ready else "degraded",
            "version": settings.version,
            "service": settings.app_name,
            "components": components,
        }

    def get_conversation_state(self, conversation_id: str) -> EnvironmentalState:
        """Retrieves the consolidated environmental state for a specific conversation ID."""
        return self.state_manager.get_state(conversation_id)


def get_chat_service(request: Request) -> EnvironmentalChatService:
    """
    FastAPI dependency provider for EnvironmentalChatService.
    Retrieves the application-scoped service instance from app.state if available,
    or instantiates a new instance.
    Can be overridden in tests via app.dependency_overrides[get_chat_service].
    """
    if hasattr(request.app, "state") and hasattr(request.app.state, "chat_service"):
        return request.app.state.chat_service
    return EnvironmentalChatService()
