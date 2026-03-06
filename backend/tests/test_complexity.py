"""
tests/test_complexity.py — Complexity Analyzer Unit Tests
-----------------------------------------------------------
Tests validate the rule-based ComplexityAnalyzer against manually constructed
ASTSummary objects. No parser or LLM calls are made — pure domain logic.

To run: pytest backend/tests/ -v
"""

import pytest
from analysis.complexity import ComplexityAnalyzer
from api.models.schemas import ASTSummary, FunctionInfo


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def analyzer() -> ComplexityAnalyzer:
    return ComplexityAnalyzer()


def make_summary(
    loop_count: int = 0,
    max_loop_depth: int = 0,
    has_recursion: bool = False,
    functions: list[FunctionInfo] | None = None,
    conditional_count: int = 0,
) -> ASTSummary:
    """Helper to build ASTSummary objects for test parameterization."""
    return ASTSummary(
        functions=functions or [],
        loop_count=loop_count,
        max_loop_depth=max_loop_depth,
        conditional_count=conditional_count,
        has_recursion=has_recursion,
        language="python",
        node_count=max(loop_count * 5, 10),
    )


# ── O(1) tests ────────────────────────────────────────────────────────────────

class TestConstantComplexity:
    def test_no_loops_no_recursion(self, analyzer):
        summary = make_summary(loop_count=0, max_loop_depth=0, has_recursion=False)
        result = analyzer.estimate(summary)
        assert result.estimate == "O(1)"
        assert result.confidence == "high"

    def test_o1_has_reasoning(self, analyzer):
        result = analyzer.estimate(make_summary())
        assert len(result.reasoning) > 10  # Not empty


# ── O(n) tests ────────────────────────────────────────────────────────────────

class TestLinearComplexity:
    def test_single_loop(self, analyzer):
        summary = make_summary(loop_count=1, max_loop_depth=1)
        result = analyzer.estimate(summary)
        assert result.estimate == "O(n)"
        assert result.confidence == "high"

    def test_multiple_sequential_loops(self, analyzer):
        """Two loops at depth 1 are still O(n) — sequential, not nested."""
        summary = make_summary(loop_count=3, max_loop_depth=1)
        result = analyzer.estimate(summary)
        assert result.estimate == "O(n)"


# ── O(n²) tests ───────────────────────────────────────────────────────────────

class TestQuadraticComplexity:
    def test_nested_loops(self, analyzer):
        summary = make_summary(loop_count=2, max_loop_depth=2)
        result = analyzer.estimate(summary)
        assert "n²" in result.estimate or "n^2" in result.estimate or "quadratic" in result.estimate.lower() \
               or result.estimate == "O(n²)"
        assert result.confidence == "high"

    def test_recursion_with_loop(self, analyzer):
        summary = make_summary(loop_count=1, max_loop_depth=1, has_recursion=True)
        result = analyzer.estimate(summary)
        assert "n²" in result.estimate or "quadratic" in result.estimate.lower()

    def test_recursion_with_deep_loops(self, analyzer):
        summary = make_summary(loop_count=2, max_loop_depth=2, has_recursion=True)
        result = analyzer.estimate(summary)
        # Should report O(n²) or worse
        assert "n²" in result.estimate or "worse" in result.estimate


# ── O(n³) tests ───────────────────────────────────────────────────────────────

class TestCubicComplexity:
    def test_triple_nested_loops(self, analyzer):
        summary = make_summary(loop_count=3, max_loop_depth=3)
        result = analyzer.estimate(summary)
        assert "n³" in result.estimate or "cubic" in result.estimate.lower() \
               or "worse" in result.estimate


# ── Recursive / logarithmic tests ─────────────────────────────────────────────

class TestRecursiveComplexity:
    def test_recursion_no_loops_single_function(self, analyzer):
        fns = [FunctionInfo(name="factorial", start_line=1, end_line=3, parameters=["n"], is_recursive=True)]
        summary = make_summary(loop_count=0, has_recursion=True, functions=fns)
        result = analyzer.estimate(summary)
        # Single recursive function without loops → log n or linear
        assert "log" in result.estimate.lower() or "n" in result.estimate

    def test_recursion_no_loops_multiple_functions(self, analyzer):
        fns = [
            FunctionInfo(name="merge_sort", start_line=1, end_line=10, parameters=["arr"], is_recursive=True),
            FunctionInfo(name="merge", start_line=12, end_line=25, parameters=["left", "right"]),
        ]
        summary = make_summary(loop_count=0, has_recursion=True, functions=fns)
        result = analyzer.estimate(summary)
        # Multiple functions + recursion → likely O(n log n)
        assert "log" in result.estimate.lower()


# ── Confidence tests ──────────────────────────────────────────────────────────

class TestConfidence:
    @pytest.mark.parametrize("depth,expected_confidence", [
        (0, "high"),   # O(1) — certain
        (1, "high"),   # O(n) — certain
        (2, "high"),   # O(n²) — certain
    ])
    def test_high_confidence_cases(self, analyzer, depth, expected_confidence):
        summary = make_summary(loop_count=depth, max_loop_depth=depth)
        result = analyzer.estimate(summary)
        assert result.confidence == expected_confidence

    def test_low_confidence_recursive(self, analyzer):
        fns = [FunctionInfo(name="search", start_line=1, end_line=5, parameters=["arr", "n"], is_recursive=True)]
        summary = make_summary(has_recursion=True, functions=fns)
        result = analyzer.estimate(summary)
        # Recursive with no loops — hard to determine exactly
        assert result.confidence in ("low", "medium")
