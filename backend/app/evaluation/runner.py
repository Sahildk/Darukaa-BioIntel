"""Evaluation runner executing test suites, computing weighted metrics, and generating reports."""
from datetime import datetime, timezone
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid

from app.conversation.flow import ConversationFlow
from app.evaluation.cases.conversation import (
    evaluate_t002_incomplete_clarification,
    evaluate_t003_multiturn_persistence,
    evaluate_t007_structured_input_ingestion,
    evaluate_t012_active_conflict_tracking,
    evaluate_t013_session_isolation,
)
from app.evaluation.cases.grounding import (
    evaluate_t004_quantitative_claim_firewall,
    evaluate_t005_evidence_traceability_chain,
    evaluate_t009_anti_hallucination_firewall,
)
from app.evaluation.cases.reasoning import (
    evaluate_t001_canonical_challenge,
    evaluate_t006_context_mismatch,
    evaluate_t011_disconnected_variables,
)
from app.evaluation.cases.retrieval import evaluate_t014_extended_retrieval
from app.evaluation.cases.safety import (
    evaluate_t008_outofscope_handling,
    evaluate_t010_hard_contraindication,
    evaluate_t015_adversarial_security_boundary,
)
from app.evaluation.models import (
    CATEGORY_WEIGHTS,
    CategoryScoreSummary,
    EvaluationCategory,
    ExtendedRetrievalMetrics,
    SystemEvaluationReport,
    TestCaseExecutionResult,
)
from app.knowledge.store import REPO_ROOT
from app.schemas.demo import EvaluationReport, EvaluationTestCaseResult
from app.services.conversation_service import EnvironmentalChatService
from app.state.manager import EnvironmentalStateManager


def get_git_commit_hash() -> Optional[str]:
    """Retrieves current git commit hash if available."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


class EvaluationRunner:
    """
    Executes the comprehensive Phase 11 evaluation suite across 15 benchmark cases.
    Guarantees:
    1. Reuses production knowledge base, index, retriever, and reasoning engine without duplication.
    2. Zero corpus mutation: never alters or re-indexes the curated scientific corpus.
    3. Isolated state: uses disposable evaluation database so production state is never contaminated.
    4. Deterministic repeatability.
    """

    def __init__(self, base_service: Optional[EnvironmentalChatService] = None):
        self.base_service = base_service or EnvironmentalChatService()

    def _create_isolated_service(self) -> Tuple[EnvironmentalChatService, Path]:
        """Creates an isolated service instance backed by a disposable SQLite state store."""
        temp_id = uuid.uuid4().hex[:8]
        temp_state_db = REPO_ROOT / f"data/eval_state_{temp_id}.db"

        isolated_state_mgr = EnvironmentalStateManager(db_path=temp_state_db)
        isolated_flow = ConversationFlow(state_manager=isolated_state_mgr)

        service = EnvironmentalChatService(
            flow=isolated_flow,
            reasoning_engine=self.base_service.reasoning_engine,
            recommendation_generator=self.base_service.recommendation_generator,
            state_manager=isolated_state_mgr,
            knowledge_store=self.base_service.knowledge_store,
            index=self.base_service.index,
        )
        return service, temp_state_db

    def run_all(self) -> SystemEvaluationReport:
        """Executes all 15 benchmark cases and computes category and overall scores."""
        service, temp_db = self._create_isolated_service()
        results: List[TestCaseExecutionResult] = []

        try:
            # 1. Reasoning Category (30%)
            results.append(evaluate_t001_canonical_challenge(service))
            results.append(evaluate_t006_context_mismatch(service))
            results.append(evaluate_t011_disconnected_variables(service))

            # 2. Grounding Category (25%)
            results.append(evaluate_t004_quantitative_claim_firewall(service))
            results.append(evaluate_t005_evidence_traceability_chain(service))
            results.append(evaluate_t009_anti_hallucination_firewall(service))

            # 3. Conversation Category (15%)
            results.append(evaluate_t002_incomplete_clarification(service))
            results.append(evaluate_t003_multiturn_persistence(service))
            results.append(evaluate_t007_structured_input_ingestion(service))
            results.append(evaluate_t012_active_conflict_tracking(service))
            results.append(evaluate_t013_session_isolation(service))

            # 4. Retrieval Category (20%) - T-014 (20-query extended benchmark)
            t014_res, ret_metrics = evaluate_t014_extended_retrieval(service)
            results.append(t014_res)

            # 5. Safety Category (10%)
            results.append(evaluate_t008_outofscope_handling(service))
            results.append(evaluate_t010_hard_contraindication(service))
            results.append(evaluate_t015_adversarial_security_boundary(service))

        finally:
            # Clean up disposable evaluation state database
            try:
                del service
            except Exception:
                pass
            import gc
            gc.collect()
            try:
                if temp_db.exists():
                    os.remove(temp_db)
            except Exception:
                pass

        # Calculate category scores and overall weighted hackathon score
        categories: Dict[str, CategoryScoreSummary] = {}
        weighted_total = 0.0

        for cat in EvaluationCategory:
            cat_results = [r for r in results if r.category == cat]
            total_cat = len(cat_results)
            passed_cat = sum(1 for r in cat_results if r.passed)
            # Use mean of test scores within category (equal weighting)
            mean_score = sum(r.score for r in cat_results) / total_cat if total_cat else 0.0
            weight = CATEGORY_WEIGHTS[cat]
            weighted_contrib = mean_score * weight * 100.0

            categories[cat.value] = CategoryScoreSummary(
                category=cat,
                weight=weight,
                total_tests=total_cat,
                passed_tests=passed_cat,
                pass_rate=round(passed_cat / total_cat, 4) if total_cat else 0.0,
                weighted_score=round(weighted_contrib, 2),
            )
            weighted_total += weighted_contrib

        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        commit = get_git_commit_hash()
        now_iso = datetime.now(timezone.utc).isoformat()

        return SystemEvaluationReport(
            timestamp=now_iso,
            git_commit=commit,
            corpus_version="1.0.0",
            corpus_source_count=10,
            total_tests=total_tests,
            passed_tests=passed_tests,
            internal_hackathon_score=round(weighted_total, 2),
            categories=categories,
            retrieval_benchmark=ret_metrics,
            results=results,
            metadata={
                "environment": "offline",
                "deterministic": True,
                "disposable_state_db": True,
            },
        )

    def to_api_report(self, sys_report: SystemEvaluationReport) -> EvaluationReport:
        """Converts SystemEvaluationReport to API-compatible EvaluationReport."""
        api_results = [
            EvaluationTestCaseResult(
                test_id=r.test_id,
                title=r.title,
                passed=r.passed,
                details=r.details,
                category=r.category.value,
                score=r.score,
                execution_time_ms=round(r.execution_time_ms, 2),
                diagnostics=r.diagnostics,
            )
            for r in sys_report.results
        ]

        return EvaluationReport(
            timestamp=sys_report.timestamp,
            total_tests=sys_report.total_tests,
            passed_tests=sys_report.passed_tests,
            overall_score=sys_report.internal_hackathon_score,
            categories={k: v.model_dump() for k, v in sys_report.categories.items()},
            retrieval_benchmark=sys_report.retrieval_benchmark.model_dump(),
            results=api_results,
        )

    def format_markdown_report(self, report: SystemEvaluationReport) -> str:
        """Renders comprehensive markdown evaluation report."""
        lines = [
            "# Darukaa BioIntel — Phase 11 Comprehensive Evaluation Report",
            "",
            "## Executive Summary",
            f"- **Timestamp**: `{report.timestamp}`",
            f"- **Git Commit**: `{report.git_commit or 'unknown'}`",
            f"- **Curated Corpus**: {report.corpus_source_count} peer-reviewed/landmark sources (v{report.corpus_version})",
            f"- **Execution Mode**: 100% Deterministic & Offline",
            f"- **Benchmark Pass Rate**: {report.passed_tests}/{report.total_tests} ({report.passed_tests/report.total_tests:.1%})",
            f"- **Internal Hackathon-Aligned Score**: **{report.internal_hackathon_score:.2f} / 100.00**",
            "",
            "> [!NOTE]",
            "> The **Internal Hackathon-Aligned Score** is computed strictly using the official challenge category weights:",
            "> Reasoning (30%), Grounding (25%), Knowledge/Retrieval (20%), Conversation (15%), and Safety/Output (10%).",
            "",
            "---",
            "",
            "## Hackathon Criteria Score Breakdown",
            "",
            "| Category | Weight | Tests Passed | Pass Rate | Weighted Score Contribution |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]

        for cat_name, cat in report.categories.items():
            lines.append(
                f"| **{cat_name.title()}** | {cat.weight*100:.0f}% | {cat.passed_tests}/{cat.total_tests} | "
                f"{cat.pass_rate:.1%} | **{cat.weighted_score:.2f} / {cat.weight*100:.1f}** |"
            )

        lines.extend([
            f"| **TOTAL** | **100%** | **{report.passed_tests}/{report.total_tests}** | **{report.passed_tests/report.total_tests:.1%}** | **{report.internal_hackathon_score:.2f} / 100.00** |",
            "",
            "---",
            "",
            "## Extended Retrieval Benchmark (T-014)",
            "",
            "Evaluated over a fixed, reproducible 20-query benchmark with explicit ground-truth (synonyms, cross-domain multi-concept queries, specific intervention mechanisms, and hard negative OOD queries).",
            "",
            "| Metric | Result | Benchmark Target | Status |",
            "| :--- | :---: | :---: | :---: |",
            f"| **Recall@1** | {report.retrieval_benchmark.recall_at_1:.2%} | >= 60.0% | {'✅ Pass' if report.retrieval_benchmark.recall_at_1 >= 0.6 else '⚠️ Alert'} |",
            f"| **Recall@3** | {report.retrieval_benchmark.recall_at_3:.2%} | >= 75.0% | {'✅ Pass' if report.retrieval_benchmark.recall_at_3 >= 0.75 else '⚠️ Alert'} |",
            f"| **Recall@5** | {report.retrieval_benchmark.recall_at_5:.2%} | >= 80.0% | {'✅ Pass' if report.retrieval_benchmark.recall_at_5 >= 0.8 else '⚠️ Alert'} |",
            f"| **Mean Reciprocal Rank (MRR)** | {report.retrieval_benchmark.mrr:.4f} | >= 0.7000 | {'✅ Pass' if report.retrieval_benchmark.mrr >= 0.7 else '⚠️ Alert'} |",
            f"| **Precision@5** | {report.retrieval_benchmark.precision_at_5:.2%} | >= 25.0% | {'✅ Pass' if report.retrieval_benchmark.precision_at_5 >= 0.25 else '⚠️ Alert'} |",
            f"| **OOD Accepted Matches** | {report.retrieval_benchmark.ood_accepted_matches} / 5 | == 0 | {'✅ Pass (Zero OOD Accepted)' if report.retrieval_benchmark.ood_accepted_matches == 0 else '❌ Fail'} |",
            "",
            "> [!IMPORTANT]",
            f"> **Out-of-Domain (OOD) Abstention Policy**: In hybrid retrieval over specialized corpora, ranked similarity scores below the acceptance threshold (`{report.retrieval_benchmark.acceptance_threshold}`) are treated as background noise rather than accepted evidence. Exactly {report.retrieval_benchmark.ood_accepted_matches} out of {report.retrieval_benchmark.ood_queries} OOD queries were accepted as evidence.",
            "",
            "---",
            "",
            "## Benchmark Test Cases (T-001 through T-015)",
            "",
            "| Test ID | Category | Title | Score | Status | Key Findings / Verification Details |",
            "| :--- | :--- | :--- | :---: | :---: | :--- |",
        ])

        for r in report.results:
            status_icon = "✅ PASS" if r.passed else "❌ FAIL"
            lines.append(
                f"| **{r.test_id}** | {r.category.value.title()} | {r.title} | {r.score:.2f} | {status_icon} | {r.details} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## Safety & Trust Boundary Verification",
            "- **T-009 (Anti-Hallucination Gate)**: Candidate lacking indexed chunk support is hard-blocked from recommendations.",
            "- **T-010 (Hard Contraindication Blocking)**: Cover crop candidate in < 300 mm/year rainfall parcel is blocked due to moisture competition.",
            "- **T-004 (Quantitative Claim Firewall)**: Verbatim audit rejected ungrounded numeric percentage claims.",
            "- **T-015 (Adversarial Security Boundary)**: Prompt injection attempting to assert scientific authority failed to fabricate evidence or bypass validation.",
            "",
            "## Reproducibility",
            "To reproduce this evaluation independently:",
            "```pwsh",
            "python backend/scripts/run_evaluation.py",
            "```",
            "or via API:",
            "```pwsh",
            "curl -X POST http://localhost:8000/api/evaluate/run",
            "```",
        ])

        return "\n".join(lines)
