"""Retrieval evaluation case: T-014 Extended Retrieval Benchmark (Category Weight: 20%)."""
import time
from typing import List, Tuple

from app.evaluation.models import (
    EvaluationCategory,
    ExtendedRetrievalMetrics,
    TestCaseExecutionResult,
)
from app.evaluation.queries import (
    EVIDENCE_ACCEPTANCE_THRESHOLD,
    EXTENDED_BENCHMARK_QUERIES,
    ExtendedBenchmarkQuery,
)
from app.retrieval.hybrid import HybridRetriever
from app.services.conversation_service import EnvironmentalChatService


def evaluate_t014_extended_retrieval(service: EnvironmentalChatService) -> Tuple[TestCaseExecutionResult, ExtendedRetrievalMetrics]:
    """
    T-014: Extended Retrieval Benchmark across 20 fixed evaluation queries.
    Measures: Recall@1, Recall@3, Recall@5, MRR, Precision@5, and OOD abstention.
    """
    start_t = time.perf_counter()
    retriever: HybridRetriever = service.retriever

    in_domain_queries: List[ExtendedBenchmarkQuery] = []
    ood_queries: List[ExtendedBenchmarkQuery] = []

    for q in EXTENDED_BENCHMARK_QUERIES:
        if q.query_type == "out_of_domain":
            ood_queries.append(q)
        else:
            in_domain_queries.append(q)

    # 1. In-Domain Retrieval Evaluation (15 queries)
    recalls_1 = []
    recalls_3 = []
    recalls_5 = []
    reciprocal_ranks = []
    precisions_5 = []

    for q in in_domain_queries:
        results = retriever.retrieve(q.query_text, top_k=5)
        retrieved_source_ids = [r.source_id for r in results]
        expected_set = set(q.expected_source_ids)

        # Hits @ K
        top_1 = set(retrieved_source_ids[:1])
        top_3 = set(retrieved_source_ids[:3])
        top_5 = set(retrieved_source_ids[:5])

        recalls_1.append(1.0 if top_1.intersection(expected_set) else 0.0)
        recalls_3.append(1.0 if top_3.intersection(expected_set) else 0.0)
        recalls_5.append(1.0 if top_5.intersection(expected_set) else 0.0)

        # Reciprocal Rank (MRR)
        rr = 0.0
        for rank_idx, s_id in enumerate(retrieved_source_ids, start=1):
            if s_id in expected_set:
                rr = 1.0 / rank_idx
                break
        reciprocal_ranks.append(rr)

        # Precision @ 5
        relevant_in_top_5 = len(top_5.intersection(expected_set))
        precisions_5.append(relevant_in_top_5 / 5.0)

    # 2. Out-of-Domain Abstention Evaluation (5 queries)
    # Checks that no OOD query generates an accepted evidence match (score >= threshold)
    ood_accepted_matches = 0
    for q in ood_queries:
        results = retriever.retrieve(q.query_text, top_k=3)
        # Any result crossing the evidence acceptance threshold with domain topic match?
        for r in results:
            if r.score >= EVIDENCE_ACCEPTANCE_THRESHOLD:
                ood_accepted_matches += 1
                break

    n_in = len(in_domain_queries)
    r1_mean = sum(recalls_1) / n_in if n_in else 0.0
    r3_mean = sum(recalls_3) / n_in if n_in else 0.0
    r5_mean = sum(recalls_5) / n_in if n_in else 0.0
    mrr_mean = sum(reciprocal_ranks) / n_in if n_in else 0.0
    p5_mean = sum(precisions_5) / n_in if n_in else 0.0

    elapsed_ms = (time.perf_counter() - start_t) * 1000

    metrics = ExtendedRetrievalMetrics(
        total_queries=len(EXTENDED_BENCHMARK_QUERIES),
        in_domain_queries=n_in,
        ood_queries=len(ood_queries),
        recall_at_1=round(r1_mean, 4),
        recall_at_3=round(r3_mean, 4),
        recall_at_5=round(r5_mean, 4),
        mrr=round(mrr_mean, 4),
        precision_at_5=round(p5_mean, 4),
        ood_accepted_matches=ood_accepted_matches,
        acceptance_threshold=EVIDENCE_ACCEPTANCE_THRESHOLD,
    )

    # Scoring criteria:
    # R@5 >= 0.80, MRR >= 0.70, OOD accepted matches == 0
    passed = r5_mean >= 0.80 and mrr_mean >= 0.70 and ood_accepted_matches == 0
    score = round((r5_mean * 0.4 + mrr_mean * 0.4 + (1.0 if ood_accepted_matches == 0 else 0.0) * 0.2), 4)

    test_result = TestCaseExecutionResult(
        test_id="T-014",
        title="Extended Multi-Facet Retrieval Benchmark (20 Queries)",
        category=EvaluationCategory.RETRIEVAL,
        passed=passed,
        score=score,
        details=(
            f"20 queries evaluated: Recall@5={metrics.recall_at_5:.2%}, MRR={metrics.mrr:.4f}, "
            f"Precision@5={metrics.precision_at_5:.2%}, OOD accepted matches={ood_accepted_matches}/5 (threshold={EVIDENCE_ACCEPTANCE_THRESHOLD})."
        ),
        execution_time_ms=elapsed_ms,
        diagnostics={
            "recall_at_1": metrics.recall_at_1,
            "recall_at_3": metrics.recall_at_3,
            "recall_at_5": metrics.recall_at_5,
            "mrr": metrics.mrr,
            "precision_at_5": metrics.precision_at_5,
            "ood_accepted_matches": ood_accepted_matches,
        },
    )

    return test_result, metrics
