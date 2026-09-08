"""Comprehensive Phase 11 evaluation test suite.

Validates:
1. Execution of all 15 benchmark test cases across the 5 official hackathon criteria.
2. Mathematical correctness of category and overall weighted hackathon score calculations.
3. Deterministic repeatability of evaluation runs.
4. Critical safety firewalls (T-004, T-009, T-010, T-015).
5. State isolation and zero contamination of production storage.
6. Extended 20-query retrieval benchmark metrics and OOD abstention policy.
7. Live API endpoint (POST /api/evaluate/run) contract and execution.
"""
from pathlib import Path
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.evaluation.models import (
    CATEGORY_WEIGHTS,
    EvaluationCategory,
    ExtendedRetrievalMetrics,
    SystemEvaluationReport,
)
from app.evaluation.runner import EvaluationRunner
from app.knowledge.store import REPO_ROOT
from app.main import app
from app.services.conversation_service import EnvironmentalChatService


@pytest.fixture
def client():
    """Provides a fresh FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def eval_runner():
    """Provides an EvaluationRunner configured with application-scoped reusable components."""
    chat_service = EnvironmentalChatService()
    return EvaluationRunner(base_service=chat_service)


# =============================================================================
# 1. 15 Benchmark Cases Execution & Schema Validity
# =============================================================================

def test_all_15_evaluation_test_cases_execute_and_return_valid_schemas(eval_runner):
    """
    Verify that EvaluationRunner executes all 15 test cases (T-001 through T-015)
    and returns a fully populated, valid SystemEvaluationReport.
    """
    report = eval_runner.run_all()

    assert isinstance(report, SystemEvaluationReport)
    assert report.total_tests == 15
    assert len(report.results) == 15

    expected_ids = {f"T-{i:03d}" for i in range(1, 16)}
    actual_ids = {r.test_id for r in report.results}
    assert actual_ids == expected_ids

    # Validate schema fields on every individual test result
    for r in report.results:
        assert isinstance(r.test_id, str) and r.test_id.startswith("T-")
        assert isinstance(r.title, str) and len(r.title) > 0
        assert isinstance(r.category, EvaluationCategory)
        assert isinstance(r.passed, bool)
        assert 0.0 <= r.score <= 1.0
        assert isinstance(r.details, str) and len(r.details) > 0
        assert r.execution_time_ms >= 0.0
        assert isinstance(r.diagnostics, dict)


# =============================================================================
# 2. Mathematical Validity of Category and Overall Scores
# =============================================================================

def test_evaluation_metrics_mathematical_validity(eval_runner):
    """
    Verify that category weighted scores and internal hackathon scores are calculated
    strictly according to the official hackathon weights (30/25/20/15/10).
    """
    report = eval_runner.run_all()

    # Category weight summation must equal 1.0 (100%)
    assert sum(CATEGORY_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-5)

    # Verify each category summary matches individual test results
    recomputed_total = 0.0
    for cat_name, cat_summary in report.categories.items():
        cat_enum = EvaluationCategory(cat_name)
        cat_tests = [r for r in report.results if r.category == cat_enum]

        assert cat_summary.total_tests == len(cat_tests)
        assert cat_summary.passed_tests == sum(1 for r in cat_tests if r.passed)
        assert cat_summary.weight == CATEGORY_WEIGHTS[cat_enum]

        mean_score = sum(r.score for r in cat_tests) / len(cat_tests) if cat_tests else 0.0
        expected_weighted = round(mean_score * cat_summary.weight * 100.0, 2)
        assert cat_summary.weighted_score == pytest.approx(expected_weighted, abs=0.05)

        recomputed_total += cat_summary.weighted_score

    # Overall score must be bounded and match recomputed sum
    assert 0.0 <= report.internal_hackathon_score <= 100.0
    assert report.internal_hackathon_score == pytest.approx(round(recomputed_total, 2), abs=0.1)


# =============================================================================
# 3. Deterministic Repeatability
# =============================================================================

def test_evaluation_is_deterministic_and_repeatable(eval_runner):
    """
    Verify that running the evaluation suite multiple times in succession
    yields identical results, test passes, and score distributions.
    """
    report1 = eval_runner.run_all()
    report2 = eval_runner.run_all()

    assert report1.total_tests == report2.total_tests
    assert report1.passed_tests == report2.passed_tests
    assert report1.internal_hackathon_score == report2.internal_hackathon_score

    # Verify case-by-case determinism
    for r1, r2 in zip(report1.results, report2.results):
        assert r1.test_id == r2.test_id
        assert r1.passed == r2.passed
        assert r1.score == r2.score


# =============================================================================
# 4. Critical Safety & Anti-Hallucination Firewalls
# =============================================================================

def test_critical_safety_firewalls_pass(eval_runner):
    """
    Ensures that essential trust boundaries, anti-hallucination gates, and contraindication
    checks pass with 100% fidelity.
    """
    report = eval_runner.run_all()
    results_by_id = {r.test_id: r for r in report.results}

    # T-004: Quantitative claim firewall (unbacked numeric percentage rejected)
    assert results_by_id["T-004"].passed is True
    assert results_by_id["T-004"].score == 1.0

    # T-009: Anti-hallucination gate (unindexed chunk ID blocked)
    assert results_by_id["T-009"].passed is True
    assert results_by_id["T-009"].score == 1.0

    # T-010: Hard contraindication blocking (< 300 mm cover crops blocked)
    assert results_by_id["T-010"].passed is True
    assert results_by_id["T-010"].score == 1.0

    # T-015: Adversarial security boundary (prompt injection cannot fabricate authority)
    assert results_by_id["T-015"].passed is True
    assert results_by_id["T-015"].score == 1.0


# =============================================================================
# 5. State Isolation & Zero Production Contamination
# =============================================================================

def test_evaluation_state_isolation(eval_runner):
    """
    Verify that the evaluation harness runs in complete isolation using disposable databases
    and does not mutate or contaminate the production state database.
    """
    prod_db = REPO_ROOT / "data/state.db"
    initial_obs_count = 0
    if prod_db.exists():
        with sqlite3.connect(prod_db) as conn:
            initial_obs_count = conn.execute("SELECT COUNT(*) FROM observation_history").fetchone()[0]

    # Run full evaluation
    eval_runner.run_all()

    # Verify production observations count has not increased
    if prod_db.exists():
        with sqlite3.connect(prod_db) as conn:
            after_obs_count = conn.execute("SELECT COUNT(*) FROM observation_history").fetchone()[0]
        assert after_obs_count == initial_obs_count

    # Verify no dangling eval_state_*.db temporary files remain in data/
    dangling_eval_dbs = list(REPO_ROOT.glob("data/eval_state_*.db"))
    assert len(dangling_eval_dbs) == 0


# =============================================================================
# 6. Extended 20-Query Retrieval Benchmark Metrics
# =============================================================================

def test_extended_retrieval_benchmark_metrics(eval_runner):
    """
    Verify the 20-query extended retrieval benchmark (T-014) metrics:
    Recall@1, Recall@3, Recall@5, MRR, Precision@5, and OOD abstention.
    """
    report = eval_runner.run_all()
    ret: ExtendedRetrievalMetrics = report.retrieval_benchmark

    assert ret.total_queries == 20
    assert ret.in_domain_queries == 15
    assert ret.ood_queries == 5

    # Target thresholds:
    assert ret.recall_at_5 >= 0.80
    assert ret.mrr >= 0.70
    assert ret.precision_at_5 >= 0.20

    # Strict OOD abstention policy:
    assert ret.ood_accepted_matches == 0
    assert ret.acceptance_threshold == 0.50


# =============================================================================
# 7. Live API Route Integration (POST /api/evaluate/run)
# =============================================================================

def test_api_evaluate_run_endpoint_returns_live_report(client):
    """
    Verify that the live FastAPI route POST /api/evaluate/run executes the EvaluationRunner
    and returns an EvaluationReport conforming to api contracts.
    """
    response = client.post("/api/evaluate/run")
    assert response.status_code == 200
    data = response.json()

    assert "timestamp" in data
    assert data["total_tests"] == 15
    assert data["passed_tests"] >= 14
    assert data["overall_score"] >= 85.0
    assert "categories" in data
    assert "retrieval_benchmark" in data
    assert len(data["results"]) == 15

    # Verify structure of test results from API
    for item in data["results"]:
        assert "test_id" in item
        assert "title" in item
        assert "passed" in item
        assert "score" in item
        assert "category" in item
        assert "execution_time_ms" in item
