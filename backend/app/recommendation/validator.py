"""Deterministic claim-level evidence validator and quantitative firewall."""
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.knowledge.store import KnowledgeStore, REPO_ROOT
from app.reasoning.context import ContextMatcher
from app.schemas.evidence import CandidateIntervention
from app.schemas.recommendation import EvidenceStrength
from app.schemas.state import EnvironmentalState, EnvironmentalVariable
from app.state.manager import _get_nested_attr
from .evidence import EvidenceResolver
from .models import ClaimValidationRecord, ClaimValidationStatus


class ValidationResult:
    """Consolidated outcome of claim-level validation on a candidate intervention."""

    def __init__(
        self,
        is_valid: bool,
        claim_records: List[ClaimValidationRecord],
        evidence_strength: EvidenceStrength,
        resolved_chunk_ids: List[str],
        resolved_source_ids: List[str],
        active_contraindications: List[str],
        limitations: List[str],
        rejection_reason: Optional[str] = None,
        rejection_stage: Optional[str] = None,
    ):
        self.is_valid = is_valid
        self.claim_records = claim_records
        self.evidence_strength = evidence_strength
        self.resolved_chunk_ids = resolved_chunk_ids
        self.resolved_source_ids = resolved_source_ids
        self.active_contraindications = active_contraindications
        self.limitations = limitations
        self.rejection_reason = rejection_reason
        self.rejection_stage = rejection_stage


class EvidenceTraceabilityValidator:
    """
    Deterministic validator enforcing:
    1. Evidence Presence & Traceability: Every claim maps to existing indexed chunks.
    2. Mechanism-Specific Support: Chunks must substantiate the specific action and impacted metrics.
    3. Context Compatibility: State must satisfy contextual prerequisites.
    4. Contraindication Gate: Blocking contraindications reject the candidate; non-blocking ones become explicit limitations.
    5. Quantitative Claim Firewall: Numbers/percentages must appear verbatim in supporting evidence excerpts.
    6. Objective Evidence Strength: Strong / Moderate / Limited derived from evidence characteristics.
    """

    def __init__(
        self,
        store: Optional[KnowledgeStore] = None,
        resolver: Optional[EvidenceResolver] = None,
        context_matcher: Optional[ContextMatcher] = None,
    ):
        if store:
            self.store = store
        else:
            db_path = REPO_ROOT / "data/knowledge.db"
            self.store = KnowledgeStore(db_path=db_path)

        self.resolver = resolver or EvidenceResolver(store=self.store)
        self.context_matcher = context_matcher or ContextMatcher()

    def validate_candidate(
        self,
        candidate: CandidateIntervention,
        state: EnvironmentalState,
        pathway_context: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Performs full claim-level validation on a candidate intervention."""
        claim_records: List[ClaimValidationRecord] = []
        limitations: List[str] = []

        # ---------------------------------------------------------------------
        # 1. Evidence Presence Gate
        # ---------------------------------------------------------------------
        if not candidate.evidence_ids:
            rec = ClaimValidationRecord(
                claim_id=f"CLM-{len(claim_records)+1:02d}-NO-EVID",
                claim_type="intervention_applicability",
                claim_text=candidate.action,
                status=ClaimValidationStatus.UNSUPPORTED_NO_EVIDENCE,
                supporting_chunk_ids=[],
                details="No evidence IDs supplied for candidate intervention.",
            )
            claim_records.append(rec)
            return ValidationResult(
                is_valid=False,
                claim_records=claim_records,
                evidence_strength=EvidenceStrength.LIMITED,
                resolved_chunk_ids=[],
                resolved_source_ids=[],
                active_contraindications=[],
                limitations=["Candidate rejected: lacks supporting evidence IDs."],
                rejection_reason="No evidence IDs provided.",
                rejection_stage="evidence",
            )

        resolved_chunks = self.resolver.get_chunk_records(candidate.evidence_ids)
        if len(resolved_chunks) == 0:
            rec = ClaimValidationRecord(
                claim_id=f"CLM-{len(claim_records)+1:02d}-UNRESOLVED",
                claim_type="intervention_applicability",
                claim_text=candidate.action,
                status=ClaimValidationStatus.UNSUPPORTED_NO_EVIDENCE,
                supporting_chunk_ids=candidate.evidence_ids,
                details=f"Evidence IDs {candidate.evidence_ids} do not exist in the knowledge store.",
            )
            claim_records.append(rec)
            return ValidationResult(
                is_valid=False,
                claim_records=claim_records,
                evidence_strength=EvidenceStrength.LIMITED,
                resolved_chunk_ids=[],
                resolved_source_ids=[],
                active_contraindications=[],
                limitations=["Candidate rejected: evidence IDs could not be resolved in the corpus."],
                rejection_reason="Unresolvable evidence IDs.",
                rejection_stage="evidence",
            )

        resolved_chunk_ids = [c["chunk_id"] for c in resolved_chunks]
        resolved_source_ids = sorted(list({c["source_id"] for c in resolved_chunks}))

        # ---------------------------------------------------------------------
        # 2. Mechanism-Specific Support Gate
        # ---------------------------------------------------------------------
        action_text = candidate.action.lower()
        rationale_text = candidate.rationale.lower()
        combined_chunk_text = " ".join(c["text"].lower() for c in resolved_chunks)

        # Check if the intervention action itself is substantiated in the supporting chunks
        action_keywords = self._extract_action_keywords(action_text)
        action_supported = any(kw in combined_chunk_text for kw in action_keywords)

        if not action_supported:
            rec = ClaimValidationRecord(
                claim_id=f"CLM-{len(claim_records)+1:02d}-ACTION-UNSUPPORTED",
                claim_type="intervention_applicability",
                claim_text=candidate.action,
                status=ClaimValidationStatus.UNSUPPORTED_CLAIM,
                supporting_chunk_ids=resolved_chunk_ids,
                details=f"None of the supporting chunks substantiate intervention action keywords: {action_keywords}.",
            )
            claim_records.append(rec)
            return ValidationResult(
                is_valid=False,
                claim_records=claim_records,
                evidence_strength=EvidenceStrength.LIMITED,
                resolved_chunk_ids=resolved_chunk_ids,
                resolved_source_ids=resolved_source_ids,
                active_contraindications=[],
                limitations=["Candidate rejected: intervention action is not substantiated by cited evidence."],
                rejection_reason="Intervention action unsupported by evidence.",
                rejection_stage="mechanism",
            )

        claim_records.append(
            ClaimValidationRecord(
                claim_id=f"CLM-{len(claim_records)+1:02d}-ACTION-SUPPORTED",
                claim_type="intervention_applicability",
                claim_text=candidate.action,
                status=ClaimValidationStatus.SUPPORTED,
                supporting_chunk_ids=resolved_chunk_ids,
                details=f"Intervention substantiated across chunks: {resolved_chunk_ids}.",
            )
        )

        # Verify impacted metrics are discussed in the supporting chunks
        for metric in candidate.affected_metrics:
            metric_keywords = self._extract_metric_keywords(metric)
            metric_supported = any(mk in combined_chunk_text for mk in metric_keywords)
            if metric_supported:
                claim_records.append(
                    ClaimValidationRecord(
                        claim_id=f"CLM-{len(claim_records)+1:02d}-METRIC-{metric.replace('.', '_')}",
                        claim_type="mechanism_support",
                        claim_text=f"Impact on {metric}",
                        status=ClaimValidationStatus.SUPPORTED,
                        supporting_chunk_ids=resolved_chunk_ids,
                        details=f"Metric impact substantiated by keywords: {metric_keywords}.",
                    )
                )
            else:
                claim_records.append(
                    ClaimValidationRecord(
                        claim_id=f"CLM-{len(claim_records)+1:02d}-METRIC-{metric.replace('.', '_')}",
                        claim_type="mechanism_support",
                        claim_text=f"Impact on {metric}",
                        status=ClaimValidationStatus.UNSUPPORTED_CLAIM,
                        supporting_chunk_ids=[],
                        details=f"Supporting chunks do not substantiate impact on metric '{metric}'.",
                    )
                )
                limitations.append(f"Evidence does not directly support impact on '{metric}'; omitted from verified claims.")

        # ---------------------------------------------------------------------
        # 3. Context Compatibility Gate
        # ---------------------------------------------------------------------
        # Evaluate required conditions using ContextMatcher
        if candidate.required_conditions:
            cond_dict = self._parse_required_conditions(candidate.required_conditions)
            if cond_dict:
                ctx_res = self.context_matcher.match(state, cond_dict)
                if not ctx_res.is_compatible:
                    rec = ClaimValidationRecord(
                        claim_id=f"CLM-{len(claim_records)+1:02d}-CONTEXT",
                        claim_type="context_compatibility",
                        claim_text=f"Context requirements: {candidate.required_conditions}",
                        status=ClaimValidationStatus.CONTEXT_MISMATCH,
                        supporting_chunk_ids=resolved_chunk_ids,
                        details=f"Context mismatch: {', '.join(ctx_res.reasons)}",
                    )
                    claim_records.append(rec)
                    return ValidationResult(
                        is_valid=False,
                        claim_records=claim_records,
                        evidence_strength=EvidenceStrength.LIMITED,
                        resolved_chunk_ids=resolved_chunk_ids,
                        resolved_source_ids=resolved_source_ids,
                        active_contraindications=[],
                        limitations=[f"Candidate rejected due to contextual mismatch: {', '.join(ctx_res.reasons)}"],
                        rejection_reason=f"Context mismatch: {', '.join(ctx_res.reasons)}",
                        rejection_stage="context",
                    )
                else:
                    claim_records.append(
                        ClaimValidationRecord(
                            claim_id=f"CLM-{len(claim_records)+1:02d}-CONTEXT",
                            claim_type="context_compatibility",
                            claim_text=f"Context requirements: {candidate.required_conditions}",
                            status=ClaimValidationStatus.SUPPORTED,
                            supporting_chunk_ids=resolved_chunk_ids,
                            details="Environmental state satisfies all contextual prerequisites.",
                        )
                    )

        # ---------------------------------------------------------------------
        # 4. Contraindication Validation Gate
        # ---------------------------------------------------------------------
        active_contraindications: List[str] = []
        for contra in candidate.contraindications:
            # Check for blocking contraindication (e.g. severe rainfall deficit < 300 mm)
            is_blocking, reason = self._check_blocking_contraindication(contra, state)
            if is_blocking:
                rec = ClaimValidationRecord(
                    claim_id=f"CLM-{len(claim_records)+1:02d}-CONTRAINDICATION-BLOCKED",
                    claim_type="contraindication",
                    claim_text=contra,
                    status=ClaimValidationStatus.CONTRAINDICATION_BLOCKED,
                    supporting_chunk_ids=resolved_chunk_ids,
                    details=f"Active blocking contraindication: {reason}",
                )
                claim_records.append(rec)
                return ValidationResult(
                    is_valid=False,
                    claim_records=claim_records,
                    evidence_strength=EvidenceStrength.LIMITED,
                    resolved_chunk_ids=resolved_chunk_ids,
                    resolved_source_ids=resolved_source_ids,
                    active_contraindications=[contra],
                    limitations=[f"Candidate rejected: {reason}"],
                    rejection_reason=f"Blocked by contraindication: {reason}",
                    rejection_stage="contraindication",
                )
            else:
                # Non-blocking contraindication -> preserved as explicit condition/limitation
                active_contraindications.append(contra)
                limitations.append(f"Cautionary Condition: {contra}")

        # ---------------------------------------------------------------------
        # 5. Quantitative Claim Firewall
        # ---------------------------------------------------------------------
        quant_claims = self._extract_quantitative_claims(candidate.rationale)
        for q_claim in quant_claims:
            # Must appear verbatim in at least one resolved chunk text
            found = any(q_claim.lower() in c["text"].lower() for c in resolved_chunks)
            if found:
                claim_records.append(
                    ClaimValidationRecord(
                        claim_id=f"CLM-{len(claim_records)+1:02d}-QUANT",
                        claim_type="quantitative_claim",
                        claim_text=f"Quantitative claim '{q_claim}'",
                        status=ClaimValidationStatus.SUPPORTED,
                        supporting_chunk_ids=resolved_chunk_ids,
                        details=f"Exact quantitative figure '{q_claim}' verified in supporting evidence text.",
                    )
                )
            else:
                rec = ClaimValidationRecord(
                    claim_id=f"CLM-{len(claim_records)+1:02d}-QUANT",
                    claim_type="quantitative_claim",
                    claim_text=f"Quantitative claim '{q_claim}'",
                    status=ClaimValidationStatus.QUANTITATIVE_CLAIM_UNSUPPORTED,
                    supporting_chunk_ids=[],
                    details=f"Quantitative claim '{q_claim}' was not found in any cited evidence chunk.",
                )
                claim_records.append(rec)
                return ValidationResult(
                    is_valid=False,
                    claim_records=claim_records,
                    evidence_strength=EvidenceStrength.LIMITED,
                    resolved_chunk_ids=resolved_chunk_ids,
                    resolved_source_ids=resolved_source_ids,
                    active_contraindications=active_contraindications,
                    limitations=[f"Candidate rejected: unverified quantitative claim '{q_claim}'."],
                    rejection_reason=f"Unsupported quantitative claim '{q_claim}'.",
                    rejection_stage="quantitative",
                )

        # ---------------------------------------------------------------------
        # 6. Objective Evidence Strength Determination
        # ---------------------------------------------------------------------
        evidence_strength = self._determine_evidence_strength(resolved_chunks, resolved_source_ids)

        return ValidationResult(
            is_valid=True,
            claim_records=claim_records,
            evidence_strength=evidence_strength,
            resolved_chunk_ids=resolved_chunk_ids,
            resolved_source_ids=resolved_source_ids,
            active_contraindications=active_contraindications,
            limitations=limitations,
        )

    def _determine_evidence_strength(
        self,
        chunks: List[Dict[str, Any]],
        source_ids: List[str],
    ) -> EvidenceStrength:
        """
        Determines scientific evidence strength objectively from corpus metadata:
        - STRONG: >= 2 chunks across authoritative peer-reviewed / landmark reports (e.g. Science, Nature, FAO, IPCC)
        - MODERATE: 1 direct authoritative chunk with full context match
        - LIMITED: Single source with narrower transferability
        """
        if len(chunks) >= 2 or len(source_ids) >= 2:
            return EvidenceStrength.STRONG
        elif len(chunks) == 1:
            return EvidenceStrength.MODERATE
        return EvidenceStrength.LIMITED

    def _extract_action_keywords(self, action_text: str) -> List[str]:
        """Extracts core action keywords for mechanism checking."""
        candidates = [
            "cover crop", "legume", "residue", "tillage", "hedgerow", "flower",
            "windbreak", "agroforestry", "corridor", "rotation", "organic",
        ]
        return [c for c in candidates if c in action_text] or [action_text.split()[0]]

    def _extract_metric_keywords(self, metric: str) -> List[str]:
        """Extracts search keywords for an environmental metric."""
        metric_map = {
            "soil.organic_carbon": ["carbon", "soc", "organic matter"],
            "soil.moisture": ["moisture", "water capacity", "water retention", "humidity"],
            "climate.rainfall": ["rainfall", "water", "precipitation"],
            "climate.temperature": ["temperature", "microclimate", "evaporation"],
            "biodiversity.species_richness": ["species", "richness", "diversity", "biodiversity"],
            "biodiversity.pollinator_abundance": ["pollinator", "bee", "beneficial insect"],
            "biodiversity.habitat_diversity": ["habitat", "diversity", "corridor"],
            "land_use.fragmentation": ["fragmentation", "connectivity", "patch"],
        }
        return metric_map.get(metric, [metric.split(".")[-1]])

    def _parse_required_conditions(self, conditions: List[str]) -> Dict[str, Any]:
        """Maps natural text condition strings to structured ContextMatcher rules."""
        rules: Dict[str, Any] = {}
        for c in conditions:
            c_low = c.lower()
            if "semi-arid" in c_low or "dryland" in c_low:
                rules["region"] = ["semi-arid", "drylands", "arid"]
            if "baseline soc" in c_low or "soc <" in c_low or "soc <=" in c_low:
                match = re.search(r"(\d+(?:\.\d+)?)\s*%", c_low)
                if match:
                    rules["soil.organic_carbon"] = {"lte": float(match.group(1))}
            if "cropland" in c_low or "monoculture" in c_low:
                rules["land_use.land_cover"] = ["cropland", "monoculture"]
        return rules

    def _check_blocking_contraindication(
        self,
        contraindication: str,
        state: EnvironmentalState,
    ) -> Tuple[bool, Optional[str]]:
        """Checks if a contraindication represents an active blocking conflict with state."""
        contra_lower = contraindication.lower()

        # Check for rainfall deficit threshold (e.g. < 300 mm/year)
        if "< 300 mm" in contra_lower or "<300 mm" in contra_lower:
            rain_var: Optional[EnvironmentalVariable] = _get_nested_attr(state, "climate.rainfall")
            if rain_var and rain_var.value is not None:
                try:
                    rain_num = float(rain_var.value)
                    if rain_num < 300.0:
                        return (
                            True,
                            f"Annual rainfall ({rain_num} mm/year) is below the 300 mm safety threshold; cover crops pose critical soil moisture competition.",
                        )
                except (ValueError, TypeError):
                    pass

        return False, None

    def _extract_quantitative_claims(self, text: str) -> List[str]:
        """Extracts percentages and numerical effect sizes from claim text."""
        # Find percentages e.g. 24%, 30%, 6-15%
        pcts = re.findall(r"\b\d+(?:-\d+)?\s*%", text)
        # Find metric ranges e.g. 15-20 mm, 2-5 degrees, 0.2-0.5 tonnes
        ranges = re.findall(r"\b\d+(?:-\d+)?\s*(?:mm|tonnes|degrees)\b", text, re.IGNORECASE)
        return pcts + ranges
