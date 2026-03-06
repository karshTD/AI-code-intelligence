"""
complexity.py — Algorithmic Complexity Estimator
--------------------------------------------------
Heuristically estimates Big-O complexity from the ASTSummary produced by the parser.

This is intentionally heuristic, not provably correct. The goal is to provide a
useful first-pass estimate that can be surfaced to developers as a hint rather than
a formal verification. The LLM layer can then refine this with natural language reasoning.

Estimation logic (ordered by decreasing complexity):
  O(n!)     — factorial / permutation patterns (not detectable from AST alone, skipped)
  O(2^n)    — recursion + branching (two recursive calls inside a branch)
  O(n²)     — two nested loops, or one loop + recursion
  O(n log n)— recursion that halves input + one loop (classic divide-and-conquer)
  O(log n)  — recursion halving input with no loops
  O(n)      — single loop, no nesting
  O(1)      — no loops, no recursion
"""

from __future__ import annotations
from api.models.schemas import ASTSummary, ComplexityInfo


class ComplexityAnalyzer:
    """
    Maps ASTSummary metrics to a Big-O estimate.

    Design note: we use a simple rule table rather than ML so the reasoning is
    explainable and the system works deterministically offline.
    """

    def estimate(self, summary: ASTSummary) -> ComplexityInfo:
        loops = summary.loop_count
        depth = summary.max_loop_depth
        recursion = summary.has_recursion

        # ── Rule table ────────────────────────────────────────────────────────
        # Rules are checked in order; first match wins.

        if recursion and depth >= 2:
            return ComplexityInfo(
                estimate="O(n²) or worse",
                reasoning=(
                    f"Detected recursion combined with {depth} levels of nested loops. "
                    "This often indicates at least quadratic growth."
                ),
                confidence="medium",
            )

        if depth >= 3:
            return ComplexityInfo(
                estimate="O(n³) or worse",
                reasoning=(
                    f"Found {depth} levels of nested loops. Triple (or deeper) nesting "
                    "typically produces cubic or worse time complexity."
                ),
                confidence="high",
            )

        if depth == 2:
            return ComplexityInfo(
                estimate="O(n²)",
                reasoning=(
                    "Detected 2 levels of nested loops. This is the classic signature of "
                    "quadratic algorithms (e.g. bubble sort, selection sort, naive matrix multiply)."
                ),
                confidence="high",
            )

        if recursion and loops == 0:
            # Check if it could be divide-and-conquer (hard to tell without semantic info)
            # We use a heuristic: if there are multiple functions, it may be divide-and-conquer
            multi_fn = len(summary.functions) > 1
            if multi_fn:
                return ComplexityInfo(
                    estimate="O(n log n) likely",
                    reasoning=(
                        "Recursion detected across multiple functions with no explicit loops. "
                        "Pattern resembles divide-and-conquer (e.g. merge sort, quicksort). "
                        "Actual complexity depends on the recurrence relation."
                    ),
                    confidence="low",
                )
            return ComplexityInfo(
                estimate="O(log n) or O(n)",
                reasoning=(
                    "Recursion without loops. If the input is halved each call this is O(log n) "
                    "(e.g. binary search). Linear recursion iterating once per element is O(n)."
                ),
                confidence="low",
            )

        if recursion and loops >= 1:
            return ComplexityInfo(
                estimate="O(n²)",
                reasoning=(
                    f"Found both recursion and {loops} loop(s). The combination typically "
                    "results in at least quadratic complexity."
                ),
                confidence="medium",
            )

        if loops == 1 and depth == 1:
            return ComplexityInfo(
                estimate="O(n)",
                reasoning=(
                    "Single non-nested loop detected. Standard linear traversal — "
                    "complexity grows proportionally to input size."
                ),
                confidence="high",
            )

        if loops > 1 and depth == 1:
            return ComplexityInfo(
                estimate="O(n)",
                reasoning=(
                    f"Found {loops} sequential (non-nested) loops. Since they run one after another "
                    "rather than nested, complexity remains O(n) — constants are dropped in Big-O."
                ),
                confidence="high",
            )

        # No loops and no recursion
        return ComplexityInfo(
            estimate="O(1)",
            reasoning=(
                "No loops or recursion detected. The code executes a fixed number of operations "
                "regardless of input size."
            ),
            confidence="high",
        )
