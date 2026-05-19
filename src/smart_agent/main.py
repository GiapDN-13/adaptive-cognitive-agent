"""Quick test runner for SmartAgent pipeline."""

import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from smart_agent.graph.builder import build_graph


def run(user_input: str) -> None:
    print(f"\n{'='*60}")
    print(f"INPUT: {user_input}")
    print("=" * 60)

    graph = build_graph()
    result = graph.invoke({"user_input": user_input})

    print(f"\n--- Perceiver ---")
    print(f"  Language: {result.get('language')} | Domains: {result.get('domains')}")
    print(f"  Complexity: {result.get('complexity_score')} | Trivial: {result.get('is_trivial')}")

    if not result.get("is_trivial") and not result.get("needs_clarification"):
        print(f"\n--- Meta-Thinker ---")
        print(f"  Persona: {result.get('persona')} | Depth: {result.get('thinking_depth')}")
        print(f"  Rules: {len(result.get('domain_rules', []))} | Gates: {len(result.get('quality_gates', []))}")

        print(f"\n--- Executor ---")
        print(f"  Iterations: {result.get('react_iterations')} | Tools used: {len(result.get('tool_calls', []))}")

        print(f"\n--- Evaluator ---")
        scores = result.get("eval_scores", {})
        print(f"  Relevance: {scores.get('relevance', '?')}")
        print(f"  Completeness: {scores.get('completeness', '?')}")
        print(f"  Accuracy: {scores.get('accuracy', '?')}")
        print(f"  Actionability: {scores.get('actionability', '?')}")
        avg = sum(scores.values()) / 4 if scores else 0
        print(f"  Average: {avg:.1f}/10 | Passed: {result.get('eval_passed')}")
        print(f"  Attempts: {result.get('attempt_number', 1)}")
        if result.get("retry_strategy"):
            print(f"  Retry strategy: {result.get('retry_strategy')}")

    print(f"\n--- Final Output ({len(result.get('final_output', ''))} chars) ---")
    print(result.get("final_output", "")[:800])
    print()


if __name__ == "__main__":
    test_cases = [
        "Xin chào",
        "Tính lãi kép: gốc 100 triệu, lãi suất 8%/năm, sau 5 năm",
        "So sánh React vs Vue cho dự án e-commerce có 10 developer, cần SSR và real-time updates",
    ]

    for case in test_cases:
        run(case)
