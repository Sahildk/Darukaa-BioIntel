"""Standalone CLI script to execute the comprehensive Phase 11 evaluation benchmark suite."""
import json
import sys
from pathlib import Path

# Ensure backend root is on sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.evaluation.runner import EvaluationRunner
from app.knowledge.store import REPO_ROOT
from app.services.conversation_service import EnvironmentalChatService


def main():
    print("=" * 78)
    print("  Darukaa BioIntel — Phase 11 Comprehensive Evaluation Benchmark")
    print("=" * 78)
    print("Initializing application components and isolated evaluation harness...\n")

    chat_service = EnvironmentalChatService()
    runner = EvaluationRunner(base_service=chat_service)

    print("Executing 15 benchmark cases across 5 official hackathon categories:")
    print("  [1] Depth of Reasoning (30%)")
    print("  [2] Scientific Grounding (25%)")
    print("  [3] Knowledge / Retrieval (20%) — 20-query extended benchmark")
    print("  [4] Conversational Intelligence (15%)")
    print("  [5] Output Clarity & Safety (10%)\n")

    report = runner.run_all()

    print("-" * 78)
    print(f"{'Category':<16} | {'Weight':<8} | {'Passed':<8} | {'Pass Rate':<10} | {'Weighted Score':<14}")
    print("-" * 78)
    for cat_name, cat in report.categories.items():
        print(
            f"{cat_name.title():<16} | {cat.weight*100:>5.0f}%  | "
            f"{cat.passed_tests}/{cat.total_tests:<6} | {cat.pass_rate:>8.1%}  | "
            f"{cat.weighted_score:>5.2f} / {cat.weight*100:<5.1f}"
        )
    print("-" * 78)
    print(
        f"{'TOTAL':<16} | 100%     | "
        f"{report.passed_tests}/{report.total_tests:<6} | {report.passed_tests/report.total_tests:>8.1%}  | "
        f"{report.internal_hackathon_score:>5.2f} / 100.00"
    )
    print("=" * 78)

    print("\n--- Extended Retrieval Benchmark (T-014) ---")
    ret = report.retrieval_benchmark
    print(f"Total Queries Evaluated:    {ret.total_queries} (15 in-domain, 5 OOD)")
    print(f"Recall@1:                   {ret.recall_at_1:.2%}")
    print(f"Recall@3:                   {ret.recall_at_3:.2%}")
    print(f"Recall@5:                   {ret.recall_at_5:.2%}")
    print(f"Mean Reciprocal Rank (MRR): {ret.mrr:.4f}")
    print(f"Precision@5:                {ret.precision_at_5:.2%}")
    print(f"OOD Accepted Matches:       {ret.ood_accepted_matches} / 5 (Threshold: {ret.acceptance_threshold})")

    print("\n--- Individual Benchmark Test Cases (T-001 - T-015) ---")
    for r in report.results:
        icon = "PASS" if r.passed else "FAIL"
        print(f"[{r.test_id}] {r.title:<55} [{icon:<4}] ({r.execution_time_ms:.1f}ms)")
        print(f"      Score: {r.score:.2f} | {r.details}")

    # Generate persistent markdown report
    md_content = runner.format_markdown_report(report)
    out_path = REPO_ROOT / "docs/EVALUATION_REPORT.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"\n[OK] Persistent markdown report generated: {out_path}")

    # Also save raw JSON report
    json_path = REPO_ROOT / "docs/evaluation_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)
    print(f"[OK] Structured JSON report generated:     {json_path}")
    print("=" * 78)


if __name__ == "__main__":
    main()
