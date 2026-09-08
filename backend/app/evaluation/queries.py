"""Fixed 20-query extended retrieval benchmark with explicit ground truth and OOD abstention policy."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ExtendedBenchmarkQuery(BaseModel):
    """An explicit retrieval benchmark query with reproducible ground-truth."""
    query_id: str
    query_text: str
    domain: str
    query_type: Literal["synonym", "multi_concept", "mechanism", "out_of_domain"]
    expected_source_ids: List[str] = Field(default_factory=list)
    description: str


# Explicit decision boundary:
# In hybrid lexical/semantic retrieval over a specialized corpus, out-of-domain queries
# may retrieve weak similarity scores on generic words ('species', 'climate', 'environmental').
# A chunk is only accepted as valid scientific evidence if its hybrid fusion relevance score
# is >= EVIDENCE_ACCEPTANCE_THRESHOLD and its indexed domain intersects with the query domain.
EVIDENCE_ACCEPTANCE_THRESHOLD = 0.50


EXTENDED_BENCHMARK_QUERIES: List[ExtendedBenchmarkQuery] = [
    # -------------------------------------------------------------------------
    # 1. Synonym & Terminology Variations (5 queries)
    # -------------------------------------------------------------------------
    ExtendedBenchmarkQuery(
        query_id="EXT-01",
        query_text="soil C sequestration in arid agrosystems",
        domain="soil_health",
        query_type="synonym",
        expected_source_ids=["SRC-FAO-2020-RECARB", "SRC-LAL-2004-SCIENCE"],
        description="Synonym variation testing carbon sequestration in dryland croplands.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-02",
        query_text="subsurface water holding capacity organic fractions",
        domain="soil_health",
        query_type="synonym",
        expected_source_ids=["SRC-FAO-2017-SOILCARBON", "SRC-LAL-2004-SCIENCE"],
        description="Synonym query testing available soil water capacity linkage to SOC.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-03",
        query_text="shelterbelts windbreak buffering topsoil erosion",
        domain="climate",
        query_type="synonym",
        expected_source_ids=["SRC-IPCC-2019-SRCCL", "SRC-KUYAH-2019-AGROFOR"],
        description="Synonym query testing perennial windbreaks and soil conservation.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-04",
        query_text="crop diversification beneficial insect pollination",
        domain="land_use",
        query_type="synonym",
        expected_source_ids=["SRC-TAMBURINI-2020-SCIADV", "SRC-GARIBALDI-2016-SCIENCE"],
        description="Synonym query testing agricultural diversification and pollination services.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-05",
        query_text="landscape connectivity hedgerows wildlife corridors",
        domain="biodiversity",
        query_type="synonym",
        expected_source_ids=["SRC-IPBES-2019-GLOBAL", "SRC-GARIBALDI-2016-SCIENCE"],
        description="Synonym query testing landscape-scale habitat corridors.",
    ),

    # -------------------------------------------------------------------------
    # 2. Multi-Concept Cross-Domain Queries (5 queries)
    # -------------------------------------------------------------------------
    ExtendedBenchmarkQuery(
        query_id="EXT-06",
        query_text="semi-arid dryland wheat monoculture soil organic carbon loss",
        domain="soil_health",
        query_type="multi_concept",
        expected_source_ids=["SRC-LAL-2004-SCIENCE", "SRC-FAO-2020-RECARB", "SRC-IPCC-2019-SRCCL"],
        description="Multi-concept query linking climate, crop monoculture, and soil degradation.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-07",
        query_text="nitrogen fixing legumes in rotation reducing drought vulnerability",
        domain="climate",
        query_type="multi_concept",
        expected_source_ids=["SRC-IPCC-2022-WG2-DRYLANDS", "SRC-FAO-2020-RECARB"],
        description="Cross-domain query linking legumes, soil fertility, and drought buffering.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-08",
        query_text="boundary trees reducing evaporation and supporting predatory insects",
        domain="land_use",
        query_type="multi_concept",
        expected_source_ids=["SRC-KUYAH-2019-AGROFOR", "SRC-IPCC-2019-SRCCL"],
        description="Cross-domain query linking agroforestry, microclimate, and biodiversity.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-09",
        query_text="plant species richness buffering crop productivity collapses during precipitation deficit",
        domain="biodiversity",
        query_type="multi_concept",
        expected_source_ids=["SRC-ISBELL-2015-NATURE", "SRC-IPCC-2022-WG2-DRYLANDS"],
        description="Cross-domain query linking species richness, drought resistance, and yield stability.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-10",
        query_text="agricultural intensification landscape fragmentation and pesticide pressure",
        domain="human_impact",
        query_type="multi_concept",
        expected_source_ids=["SRC-IPBES-2019-GLOBAL"],
        description="Multi-variable query linking human agricultural expansion, fragmentation, and biodiversity loss.",
    ),

    # -------------------------------------------------------------------------
    # 3. Specific Intervention Mechanism Queries (5 queries)
    # -------------------------------------------------------------------------
    ExtendedBenchmarkQuery(
        query_id="EXT-11",
        query_text="crop residue retention moderating soil temperature by 2 to 5 degrees",
        domain="soil_health",
        query_type="mechanism",
        expected_source_ids=["SRC-FAO-2020-RECARB"],
        description="Verifies retrieval of specific crop residue thermal moderation mechanism.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-12",
        query_text="soil organic carbon critical threshold 1.1 percent crusting",
        domain="soil_health",
        query_type="mechanism",
        expected_source_ids=["SRC-LAL-2004-SCIENCE"],
        description="Verifies retrieval of physical threshold of dryland soil degradation.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-13",
        query_text="boundary windbreaks lowering ground wind speed by 30 to 50 percent",
        domain="climate",
        query_type="mechanism",
        expected_source_ids=["SRC-IPCC-2019-SRCCL"],
        description="Verifies retrieval of boundary windbreak aerodynamic reduction mechanism.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-14",
        query_text="polyculture mulching lowering surface evaporation by 20 to 30 percent in drylands",
        domain="climate",
        query_type="mechanism",
        expected_source_ids=["SRC-IPCC-2022-WG2-DRYLANDS"],
        description="Verifies retrieval of polyculture moisture evaporation buffer mechanism.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-15",
        query_text="non-crop flowering borders closing crop yield gaps by wild pollinators",
        domain="biodiversity",
        query_type="mechanism",
        expected_source_ids=["SRC-GARIBALDI-2016-SCIENCE"],
        description="Verifies retrieval of floral margin wild pollinator yield gap mechanism.",
    ),

    # -------------------------------------------------------------------------
    # 4. Hard Negative / Out-of-Domain Queries (5 queries)
    # -------------------------------------------------------------------------
    ExtendedBenchmarkQuery(
        query_id="EXT-16",
        query_text="deep ocean coral reef bleaching symbiotic zooxanthellae thermal mortality",
        domain="marine_biology",
        query_type="out_of_domain",
        expected_source_ids=[],
        description="Hard negative marine query outside terrestrial agriculture and soil corpus.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-17",
        query_text="arctic permafrost thaw thermokarst methane emissions feedback",
        domain="polar_geology",
        query_type="out_of_domain",
        expected_source_ids=[],
        description="Hard negative polar cryosphere query outside agricultural scope.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-18",
        query_text="urban vehicle particulate matter diesel soot air quality index",
        domain="urban_pollution",
        query_type="out_of_domain",
        expected_source_ids=[],
        description="Hard negative urban transport query outside ecological restoration corpus.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-19",
        query_text="deep sea commercial bottom trawling benthic seamount sediment disruption",
        domain="fisheries",
        query_type="out_of_domain",
        expected_source_ids=[],
        description="Hard negative benthic marine query outside terrestrial land management.",
    ),
    ExtendedBenchmarkQuery(
        query_id="EXT-20",
        query_text="volcanic tephra ash plume soil sulfur acidification",
        domain="volcanology",
        query_type="out_of_domain",
        expected_source_ids=[],
        description="Hard negative volcanology query outside curated agricultural corpus.",
    ),
]
