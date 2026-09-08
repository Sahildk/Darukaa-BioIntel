"""Golden retrieval benchmark evaluating Recall@k and MRR over authentic scientific corpus."""
from typing import Dict, List, Set
from pydantic import BaseModel, Field

from .hybrid import HybridRetriever


class GoldenBenchmarkQuery(BaseModel):
    """A canonical evaluation query with ground-truth relevant source IDs."""
    query_id: str
    query_text: str
    domain: str
    expected_source_ids: List[str]


# 10 Canonical benchmark queries based strictly on the authentic corpus
GOLDEN_QUERIES: List[GoldenBenchmarkQuery] = [
    GoldenBenchmarkQuery(
        query_id="GBQ-01",
        query_text="soil organic carbon in drylands with legume cover crops",
        domain="soil_health",
        expected_source_ids=["SRC-FAO-2020-RECARB", "SRC-LAL-2004-SCIENCE"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-02",
        query_text="soil organic carbon moisture holding capacity and water retention",
        domain="soil_health",
        expected_source_ids=["SRC-FAO-2017-SOILCARBON", "SRC-LAL-2004-SCIENCE"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-03",
        query_text="continuous monoculture land degradation wind erosion shelterbelts",
        domain="climate",
        expected_source_ids=["SRC-IPCC-2019-SRCCL"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-04",
        query_text="drought frequency in rainfed drylands polyculture and mulching",
        domain="climate",
        expected_source_ids=["SRC-IPCC-2022-WG2-DRYLANDS"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-05",
        query_text="agricultural crop diversification biodiversity without compromising yield",
        domain="land_use",
        expected_source_ids=["SRC-TAMBURINI-2020-SCIADV"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-06",
        query_text="agroforestry nitrogen fixing trees dryland beneficial insects microclimate",
        domain="land_use",
        expected_source_ids=["SRC-KUYAH-2019-AGROFOR"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-07",
        query_text="wild pollinator density crop yield flowering borders hedgerows",
        domain="biodiversity",
        expected_source_ids=["SRC-GARIBALDI-2016-SCIENCE"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-08",
        query_text="plant species richness drought resistance ecosystem productivity stability",
        domain="biodiversity",
        expected_source_ids=["SRC-ISBELL-2015-NATURE"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-09",
        query_text="agricultural landscape fragmentation ecological corridors connectivity",
        domain="human_impact",
        expected_source_ids=["SRC-IPBES-2019-GLOBAL"],
    ),
    GoldenBenchmarkQuery(
        query_id="GBQ-10",
        query_text="semi-arid dryland wheat monoculture soil organic carbon low rainfall",
        domain="challenge_scenario",
        expected_source_ids=["SRC-FAO-2020-RECARB", "SRC-IPCC-2019-SRCCL", "SRC-LAL-2004-SCIENCE"],
    ),
]


class QueryBenchmarkMetric(BaseModel):
    """Evaluation metrics for a single query."""
    query_id: str
    query_text: str
    expected_sources: List[str]
    retrieved_sources: List[str]
    recall_at_k: float
    reciprocal_rank: float
    hit: bool


class GoldenBenchmarkReport(BaseModel):
    """Aggregate evaluation report over the complete golden retrieval benchmark."""
    total_queries: int
    top_k: int
    mean_recall_at_k: float
    mean_reciprocal_rank: float
    query_results: List[QueryBenchmarkMetric]


def evaluate_retriever_on_golden_set(
    retriever: HybridRetriever,
    top_k: int = 5,
    mode: str = "hybrid",
) -> GoldenBenchmarkReport:
    """
    Executes the golden benchmark queries and computes Recall@k and Mean Reciprocal Rank (MRR).
    
    Recall@k = (Count of expected sources retrieved in top_k) / (Count of expected sources)
    MRR = Average of (1 / rank of first relevant source retrieved)
    """
    metrics: List[QueryBenchmarkMetric] = []

    for item in GOLDEN_QUERIES:
        results = retriever.retrieve(item.query_text, top_k=top_k, mode=mode)
        retrieved_source_ids = [r.source_id for r in results]
        
        # Deduplicated retrieved source list preserving order
        unique_retrieved_sources: List[str] = []
        for sid in retrieved_source_ids:
            if sid not in unique_retrieved_sources:
                unique_retrieved_sources.append(sid)

        expected_set = set(item.expected_source_ids)
        matched_expected = [s for s in expected_set if s in unique_retrieved_sources]
        
        recall = len(matched_expected) / len(expected_set) if expected_set else 0.0

        # Find rank of first relevant source (1-indexed)
        first_rank: float = 0.0
        reciprocal_rank: float = 0.0
        for rank, sid in enumerate(unique_retrieved_sources, start=1):
            if sid in expected_set:
                first_rank = float(rank)
                reciprocal_rank = 1.0 / first_rank
                break

        metrics.append(
            QueryBenchmarkMetric(
                query_id=item.query_id,
                query_text=item.query_text,
                expected_sources=item.expected_source_ids,
                retrieved_sources=unique_retrieved_sources,
                recall_at_k=round(recall, 4),
                reciprocal_rank=round(reciprocal_rank, 4),
                hit=len(matched_expected) > 0,
            )
        )

    mean_recall = sum(m.recall_at_k for m in metrics) / len(metrics) if metrics else 0.0
    mean_mrr = sum(m.reciprocal_rank for m in metrics) / len(metrics) if metrics else 0.0

    return GoldenBenchmarkReport(
        total_queries=len(metrics),
        top_k=top_k,
        mean_recall_at_k=round(mean_recall, 4),
        mean_reciprocal_rank=round(mean_mrr, 4),
        query_results=metrics,
    )
