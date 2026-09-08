"""Extensible context compatibility layer for ecological reasoning."""
from typing import Any, Dict, List, Optional, Set
from app.schemas.state import EnvironmentalState, EnvironmentalVariable
from app.state.manager import _get_nested_attr
from .models import ContextMatchResult


# Regional and climatic synonym/ontology sets
REGION_ONTOLOGY: Dict[str, Set[str]] = {
    "semi-arid": {"semi-arid", "semi_arid", "drylands", "dryland", "arid", "water-limited", "rainfed_drylands"},
    "arid": {"arid", "drylands", "dryland", "hyper-arid", "water-limited"},
    "temperate": {"temperate", "sub-humid", "continental"},
    "tropical": {"tropical", "humid_tropics", "subtropical", "monsoon"},
}

# Land management ontology sets
MANAGEMENT_ONTOLOGY: Dict[str, Set[str]] = {
    "monoculture": {"monoculture", "monocrop", "simplified_rotation", "continuous_cropping"},
    "polyculture": {"polyculture", "intercropping", "diversified_rotation", "agroforestry"},
    "agroforestry": {"agroforestry", "silvopasture", "shelterbelts", "windbreaks"},
    "cropland": {"cropland", "arable", "farmland", "agricultural_land"},
}

# Crop classification ontology sets
CROP_ONTOLOGY: Dict[str, Set[str]] = {
    "wheat": {"wheat", "cereal", "small_grain", "annual_crop", "cropland"},
    "rice": {"rice", "paddy", "cereal", "cropland"},
    "corn": {"corn", "maize", "cereal", "row_crop", "cropland"},
    "maize": {"corn", "maize", "cereal", "row_crop", "cropland"},
    "barley": {"barley", "cereal", "small_grain", "annual_crop", "cropland"},
    "sorghum": {"sorghum", "millet", "cereal", "drought_tolerant", "cropland"},
}


class ContextMatcher:
    """
    Extensible deterministic evaluator of environmental context compatibility.
    Evaluates state observations against condition specifications, supporting
    range constraints, taxonomic ontologies, and categorical synonyms.
    """

    def __init__(self):
        self.region_ontology = REGION_ONTOLOGY
        self.management_ontology = MANAGEMENT_ONTOLOGY
        self.crop_ontology = CROP_ONTOLOGY

    def match(
        self,
        state: EnvironmentalState,
        conditions: Dict[str, Any],
    ) -> ContextMatchResult:
        """
        Evaluates conditions against state.
        conditions example:
        {
            "region": ["semi-arid", "drylands"],
            "soil.organic_carbon": {"lte": 1.1},
            "land_use.land_cover": ["monoculture", "cropland"]
        }
        """
        if not conditions:
            return ContextMatchResult(
                is_compatible=True,
                matched_conditions=["no_context_constraints"],
                unmatched_conditions=[],
                reasons=["No restrictive conditions specified; universal template."],
            )

        matched: List[str] = []
        unmatched: List[str] = []
        reasons: List[str] = []

        for var_path, rule in conditions.items():
            var: Optional[EnvironmentalVariable] = _get_nested_attr(state, var_path)

            if var is None or var.value is None:
                # Condition requires variable that is not in state
                unmatched.append(var_path)
                reasons.append(f"Prerequisite context variable '{var_path}' is absent from environmental state.")
                continue

            val = var.value

            # Case A: Numeric range rule e.g. {"lte": 1.0} or {"gte": 500}
            if isinstance(rule, dict):
                is_rule_satisfied = True
                try:
                    num_val = float(val)
                    if "lte" in rule and num_val > float(rule["lte"]):
                        is_rule_satisfied = False
                        reasons.append(f"'{var_path}' value {num_val} exceeds threshold <= {rule['lte']}.")
                    if "gte" in rule and num_val < float(rule["gte"]):
                        is_rule_satisfied = False
                        reasons.append(f"'{var_path}' value {num_val} is below threshold >= {rule['gte']}.")
                    if "lt" in rule and num_val >= float(rule["lt"]):
                        is_rule_satisfied = False
                        reasons.append(f"'{var_path}' value {num_val} is not < {rule['lt']}.")
                    if "gt" in rule and num_val <= float(rule["gt"]):
                        is_rule_satisfied = False
                        reasons.append(f"'{var_path}' value {num_val} is not > {rule['gt']}.")
                except (ValueError, TypeError):
                    is_rule_satisfied = False
                    reasons.append(f"Cannot perform numeric comparison on non-numeric value '{val}' for '{var_path}'.")

                if is_rule_satisfied:
                    matched.append(f"{var_path}: {rule}")
                else:
                    unmatched.append(f"{var_path}: {rule}")

            # Case B: Categorical list / ontology matching
            elif isinstance(rule, (list, set, tuple)):
                allowed_terms = {str(t).lower().strip() for t in rule}
                val_str = str(val).lower().strip()

                # Direct match
                if val_str in allowed_terms:
                    matched.append(f"{var_path} in {list(allowed_terms)}")
                    continue

                # Ontology expansion matching
                expanded_user_terms = self._expand_terms(var_path, val_str)
                if expanded_user_terms.intersection(allowed_terms):
                    matched.append(f"{var_path} ({val_str} -> {list(expanded_user_terms)}) in {list(allowed_terms)}")
                else:
                    unmatched.append(f"{var_path}: {val_str} not in {list(allowed_terms)}")
                    reasons.append(f"Context '{var_path}' value '{val_str}' does not match required categories: {list(allowed_terms)}.")

            # Case C: Scalar equality
            else:
                rule_str = str(rule).lower().strip()
                val_str = str(val).lower().strip()
                if val_str == rule_str:
                    matched.append(f"{var_path} == {rule_str}")
                else:
                    unmatched.append(f"{var_path}: {val_str} != {rule_str}")
                    reasons.append(f"Context '{var_path}' is '{val_str}', expected '{rule_str}'.")

        is_compatible = len(unmatched) == 0
        return ContextMatchResult(
            is_compatible=is_compatible,
            matched_conditions=matched,
            unmatched_conditions=unmatched,
            reasons=reasons,
        )

    def _expand_terms(self, path: str, term: str) -> Set[str]:
        """Expands a canonical term using domain-specific taxonomic ontologies."""
        expanded = {term}
        if "region" in path:
            for key, syns in self.region_ontology.items():
                if term in syns or term == key:
                    expanded.update(syns)
        elif "land_cover" in path or "land_use" in path:
            for key, syns in self.management_ontology.items():
                if term in syns or term == key:
                    expanded.update(syns)
        elif "crop" in path:
            for key, syns in self.crop_ontology.items():
                if term in syns or term == key:
                    expanded.update(syns)
        return expanded
