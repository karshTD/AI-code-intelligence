"""
tests/test_ast_parser.py — AST Parser Unit Tests
--------------------------------------------------
Tests validate the regex-fallback parser (always available, no tree-sitter
dependency required) so the CI can run these without installing grammar packages.

To run: pytest backend/tests/ -v
"""

import pytest
from analysis.ast_parser import ASTParser
from analysis.language_registry import LanguageRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def parser() -> ASTParser:
    return ASTParser()


SIMPLE_PYTHON = """\
def add(a, b):
    return a + b
"""

LOOP_PYTHON = """\
def bubble_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr) - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
"""

RECURSIVE_PYTHON = """\
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""

MULTI_FUNCTION_PYTHON = """\
def helper(x):
    return x * 2

def main(items):
    result = []
    for item in items:
        result.append(helper(item))
    return result
"""

JS_SNIPPET = """\
function greet(name) {
    return "Hello, " + name;
}
"""


# ── Function detection tests ──────────────────────────────────────────────────

class TestFunctionDetection:
    def test_detects_single_python_function(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(SIMPLE_PYTHON, lang)
        assert len(summary.functions) == 1
        assert summary.functions[0].name == "add"

    def test_detects_multiple_functions(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(MULTI_FUNCTION_PYTHON, lang)
        names = [f.name for f in summary.functions]
        assert "helper" in names
        assert "main" in names

    def test_detects_javascript_function(self, parser):
        lang = LanguageRegistry.get("javascript")
        summary = parser.parse(JS_SNIPPET, lang)
        assert len(summary.functions) >= 1
        assert summary.functions[0].name == "greet"

    def test_no_functions_empty_code(self, parser):
        summary = parser.parse("x = 1 + 2", None)
        assert summary.functions == []

    def test_language_id_set_correctly(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(SIMPLE_PYTHON, lang)
        assert summary.language == "python"


# ── Loop detection tests ──────────────────────────────────────────────────────

class TestLoopDetection:
    def test_no_loops_in_simple_function(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(SIMPLE_PYTHON, lang)
        assert summary.loop_count == 0

    def test_detects_nested_loops(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(LOOP_PYTHON, lang)
        assert summary.loop_count >= 2

    def test_max_loop_depth_nested(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(LOOP_PYTHON, lang)
        # Two nested for-loops → depth of at least 2
        assert summary.max_loop_depth >= 2

    def test_single_loop_depth_is_one(self, parser):
        code = "for i in range(10):\n    print(i)\n"
        summary = parser.parse(code, LanguageRegistry.get("python"))
        assert summary.max_loop_depth >= 1


# ── Recursion detection tests ─────────────────────────────────────────────────

class TestRecursionDetection:
    def test_detects_recursion(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(RECURSIVE_PYTHON, lang)
        assert summary.has_recursion is True

    def test_no_recursion_in_iterative_code(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(LOOP_PYTHON, lang)
        assert summary.has_recursion is False

    def test_no_recursion_in_simple_function(self, parser):
        lang = LanguageRegistry.get("python")
        summary = parser.parse(SIMPLE_PYTHON, lang)
        assert summary.has_recursion is False


# ── Node count / structural sanity ────────────────────────────────────────────

class TestStructural:
    def test_node_count_positive(self, parser):
        summary = parser.parse(LOOP_PYTHON, LanguageRegistry.get("python"))
        assert summary.node_count > 0

    def test_unknown_language_does_not_crash(self, parser):
        """Passing None as config triggers the regex fallback — must not raise."""
        summary = parser.parse("function foo() {}", None)
        assert summary is not None
