"""Completeness checking and targeted clarification generation."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.state import EnvironmentalState, EnvironmentalVariable
from app.state.manager import VALID_VARIABLE_PATHS, _get_nested_attr


CORE_HIGH_VALUE_VARIABLES: List[str] = [
    "region",
    "soil.organic_carbon",
    "climate.rainfall",
    "land_use.crop",
    "land_use.land_cover",
    "soil.ph",
    "biodiversity.habitat_diversity",
]

VARIABLE_LABELS: Dict[str, str] = {
    "region": "regional climate zone (e.g., semi-arid, temperate, tropical)",
    "soil.organic_carbon": "soil organic carbon % (SOC)",
    "soil.ph": "soil pH",
    "soil.moisture": "soil moisture level",
    "climate.rainfall": "annual rainfall pattern (e.g., low, 400 mm/year)",
    "climate.temperature": "average temperature",
    "land_use.crop": "primary crop type (e.g., wheat, maize)",
    "land_use.land_cover": "land use practice (e.g., monoculture, agroforestry)",
    "land_use.fragmentation": "land fragmentation level",
    "biodiversity.species_richness": "species richness",
    "biodiversity.habitat_diversity": "habitat or biodiversity condition",
    "biodiversity.pollinator_abundance": "pollinator abundance",
    "human_impact.pollution": "chemical pollution or pesticide pressure",
    "human_impact.deforestation": "deforestation pressure",
}


class CompletenessAssessment(BaseModel):
    """Result of assessing whether environmental state has sufficient data for reasoning."""
    is_complete: bool
    populated_variables: List[str] = Field(default_factory=list)
    missing_variables: List[str] = Field(default_factory=list)
    has_conflict: bool = False
    conflict_path: Optional[str] = None
    clarification_question: Optional[str] = None


class CompletenessChecker:
    """
    Evaluates environmental state completeness against multi-metric reasoning requirements.
    Prioritizes resolving active conflicts, detects missing high-value variables,
    and constructs targeted clarification questions without re-asking established facts.
    """

    def __init__(self, min_required_variables: int = 3, max_clarification_vars: int = 3):
        self.min_required_variables = min_required_variables
        self.max_clarification_vars = max_clarification_vars

    def get_populated_variables(self, state: EnvironmentalState) -> List[str]:
        """Returns all dotted paths that have an active, non-null value in the state."""
        populated: List[str] = []
        for path in sorted(list(VALID_VARIABLE_PATHS)):
            var = _get_nested_attr(state, path)
            if var is not None and var.value is not None and str(var.value).strip() != "":
                populated.append(path)
        return populated

    def check(self, state: EnvironmentalState) -> CompletenessAssessment:
        """Assesses state completeness, prioritizing unresolved conflicts before checking minimum variable count."""
        populated = self.get_populated_variables(state)

        # 1. Unresolved conflicts take absolute precedence for clarification
        if state.active_conflicts:
            conflict = state.active_conflicts[0]
            var_path = conflict.get("variable_path", "")
            explanation = conflict.get("explanation", "conflicting values recorded")
            question = (
                f"We noticed conflicting data for '{var_path}': {explanation}. "
                "Could you please confirm which value reflects your actual field conditions?"
            )
            return CompletenessAssessment(
                is_complete=False,
                populated_variables=populated,
                missing_variables=[var_path] if var_path else [],
                has_conflict=True,
                conflict_path=var_path,
                clarification_question=question,
            )

        # 2. Check if minimum variable threshold is met
        if len(populated) >= self.min_required_variables:
            return CompletenessAssessment(
                is_complete=True,
                populated_variables=populated,
                missing_variables=[],
                has_conflict=False,
                clarification_question=None,
            )

        # 3. Identify missing high-value variables
        populated_set = set(populated)
        missing_candidates = [v for v in CORE_HIGH_VALUE_VARIABLES if v not in populated_set]

        # Select a minimal targeted set of missing variables (e.g. enough to satisfy minimum)
        selected_count = min(len(missing_candidates), self.max_clarification_vars)
        selected_missing = missing_candidates[:selected_count]

        # Generate targeted clarification question
        question = self._generate_clarification_question(selected_missing, populated)

        return CompletenessAssessment(
            is_complete=False,
            populated_variables=populated,
            missing_variables=selected_missing,
            has_conflict=False,
            clarification_question=question,
        )

    def _generate_clarification_question(
        self,
        missing: List[str],
        populated: List[str],
    ) -> str:
        """Generates a concise, natural clarification question asking only for the targeted missing variables."""
        if not missing:
            return "Could you provide additional details about your land and environmental conditions?"

        labels = [VARIABLE_LABELS.get(m, m) for m in missing]

        if len(labels) == 1:
            return (
                f"To provide an evidence-grounded assessment, could you specify your {labels[0]}?"
            )
        elif len(labels) == 2:
            return (
                f"To tailor the ecological assessment to your land, could you please share your {labels[0]} and {labels[1]}?"
            )
        else:
            joined = ", ".join(labels[:-1]) + f", and {labels[-1]}"
            return (
                f"To assess your land health accurately, could you provide your approximate {joined}?"
            )
