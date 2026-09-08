"""Scientific sufficiency evaluator ensuring inputs form a coherent ecological nexus."""
from typing import List, Set
from app.schemas.state import EnvironmentalState, EnvironmentalVariable
from app.state.manager import _get_nested_attr, VALID_VARIABLE_PATHS
from .models import ScientificSufficiencyResult


class ScientificSufficiencyEvaluator:
    """
    Evaluates whether the provided environmental state contains a scientifically sufficient
    nexus of interdependent variables capable of supporting evidence-constrained ecological reasoning.

    Enforces the rule: 3 variables != automatically enough information.
    A disconnected set (e.g. temperature + rainfall + crop) cannot responsibly support
    biodiversity or restoration interventions without baseline soil or ecological management context.
    """

    def evaluate(self, state: EnvironmentalState) -> ScientificSufficiencyResult:
        # Collect populated variables
        populated: Set[str] = set()
        for path in VALID_VARIABLE_PATHS:
            var: EnvironmentalVariable = _get_nested_attr(state, path)
            if var is not None and var.value is not None and str(var.value).strip() != "":
                populated.add(path)

        if len(populated) < 3:
            return ScientificSufficiencyResult(
                is_scientifically_sufficient=False,
                identified_domains=[],
                matched_templates=[],
                missing_critical_context=[f"State contains only {len(populated)} variables; minimum of 3 required for multi-metric analysis."],
                evaluation_notes="Insufficient variable count for multi-metric reasoning.",
            )

        # Categorize populated variables
        has_soil = any(p.startswith("soil.") for p in populated)
        has_climate = any(p.startswith("climate.") or p == "region" for p in populated)
        has_management = any(p.startswith("land_use.") or p.startswith("human_impact.") for p in populated)
        has_biodiversity = any(p.startswith("biodiversity.") for p in populated)

        # Check for specific scientific nexuses
        identified_domains: List[str] = []

        # Nexus 1: Soil-Climate-Management (e.g. FAO Recarb, Lal 2004, Tamburini 2020)
        if has_soil and has_climate and has_management:
            identified_domains.append("soil_climate_management")

        # Nexus 2: Biodiversity-Habitat-Management (e.g. Garibaldi 2016, IPBES 2019)
        if has_biodiversity and has_management and has_climate:
            identified_domains.append("biodiversity_habitat_management")

        # Nexus 3: Soil-Biodiversity-Regime (e.g. FAO 2017, Isbell 2015)
        if has_soil and has_biodiversity:
            identified_domains.append("soil_biodiversity_dynamics")

        # Nexus 4: Landscape Fragmentation & Connectivity (e.g. IPBES 2019)
        if any("fragmentation" in p or "deforestation" in p for p in populated) and (has_biodiversity or has_management):
            identified_domains.append("landscape_connectivity")

        # Disconnected variable check (e.g. temperature + rainfall + crop, without soil or biodiversity or management practice)
        # Note: crop alone without land_cover/practice (monoculture vs polyculture) and without soil condition cannot determine soil/biodiversity degradation
        is_disconnected_crop_climate = (
            not has_soil and not has_biodiversity and
            "land_use.land_cover" not in populated and
            "land_use.fragmentation" not in populated and
            "human_impact.deforestation" not in populated
        )

        if is_disconnected_crop_climate or not identified_domains:
            missing = [
                "Baseline soil condition (e.g., soil organic carbon % or pH) or land management practice "
                "(e.g., monoculture vs. diversified cropping) is required to evaluate ecological restoration pathways; "
                "climate + crop alone is scientifically insufficient."
            ]
            return ScientificSufficiencyResult(
                is_scientifically_sufficient=False,
                identified_domains=[],
                matched_templates=[],
                missing_critical_context=missing,
                evaluation_notes="Variables present do not form a coherent scientific nexus for ecological restoration.",
            )

        return ScientificSufficiencyResult(
            is_scientifically_sufficient=True,
            identified_domains=identified_domains,
            matched_templates=[],
            missing_critical_context=[],
            evaluation_notes=f"State satisfies scientific sufficiency across domains: {', '.join(identified_domains)}.",
        )
