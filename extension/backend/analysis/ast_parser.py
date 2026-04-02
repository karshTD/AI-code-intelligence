"""
ast_parser.py — Tree-sitter AST Parser
----------------------------------------
Wraps tree-sitter to provide a clean, language-agnostic interface.

Design decisions:
- We import tree-sitter grammars lazily (inside parse()) so startup time is fast
  and only languages actually used incur the import cost.
- If a language grammar isn't installed, we fall back to regex-based heuristics
  rather than crashing. This keeps the service resilient during development.
- The ASTWalker is a recursive visitor that collects structural metrics in one
  pass over the tree (O(n) in node count).
"""

from __future__ import annotations
import logging
import re
from typing import Optional, Any

from api.models.schemas import ASTSummary, FunctionInfo
from analysis.language_registry import LanguageConfig

logger = logging.getLogger(__name__)


# ── Tree-sitter availability check ───────────────────────────────────────────

def _try_import_tree_sitter():
    """
    Attempt to import tree_sitter. Returns the module or None.
    Separating this lets us degrade gracefully without crashing at import time.
    """
    try:
        import tree_sitter  # noqa: F401
        return tree_sitter
    except ImportError:
        logger.warning("tree-sitter not installed — falling back to regex parser")
        return None


_tree_sitter = _try_import_tree_sitter()


# ── Main Parser Class ─────────────────────────────────────────────────────────

class ASTParser:
    """
    Parses source code into a structured ASTSummary.

    Usage:
        parser = ASTParser()
        summary = parser.parse(code="def foo(): pass", language_config=config)
    """

    def parse(self, code: str, language_config: Optional[LanguageConfig]) -> ASTSummary:
        """
        Entry point. Routes to tree-sitter or regex fallback based on availability.
        """
        if _tree_sitter is not None and language_config is not None:
            try:
                return self._parse_with_tree_sitter(code, language_config)
            except Exception as exc:
                logger.error("Tree-sitter parse failed (%s) — using regex fallback", exc)

        # Always have a fallback so the service keeps running
        return self._parse_with_regex(code, language_config)

    # ── Tree-sitter path ──────────────────────────────────────────────────────

    def _parse_with_tree_sitter(self, code: str, lang_config: LanguageConfig) -> ASTSummary:
        """
        Full AST parse using tree-sitter.
        Lazily loads the language grammar to avoid startup overhead.
        """
        grammar_module = self._load_grammar(lang_config.tree_sitter_module)
        if grammar_module is None:
            return self._parse_with_regex(code, lang_config)

        from tree_sitter import Parser, Language

        # Build the language object from the grammar
        lang = Language(grammar_module.language())
        parser = Parser(lang)

        tree = parser.parse(bytes(code, "utf-8"))
        walker = _ASTWalker(lang_config, code)
        walker.walk(tree.root_node)

        return ASTSummary(
            functions=walker.functions,
            loop_count=walker.loop_count,
            max_loop_depth=walker.max_loop_depth,
            conditional_count=walker.conditional_count,
            has_recursion=walker.has_recursion,
            language=lang_config.language_id,
            node_count=walker.node_count,
        )

    def _load_grammar(self, module_name: str) -> Optional[Any]:
        """Dynamically import a tree-sitter grammar package."""
        try:
            import importlib
            return importlib.import_module(module_name)
        except ImportError:
            logger.warning("Grammar module '%s' not installed", module_name)
            return None

    # ── Regex fallback path ───────────────────────────────────────────────────

    def _parse_with_regex(self, code: str, lang_config: Optional[LanguageConfig]) -> ASTSummary:
        """
        Heuristic fallback using regular expressions.
        Covers the most common structural patterns well enough for complexity estimation.
        This intentionally trades accuracy for resilience.
        """
        lines = code.splitlines()
        functions: list[FunctionInfo] = []

        # Python function detection
        py_func_re = re.compile(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)")
        js_func_re = re.compile(
            r"(?:function\s+(\w+)\s*\(([^)]*)\)|const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>)"
        )

        for i, line in enumerate(lines):
            m = py_func_re.match(line) or js_func_re.search(line)
            if m:
                name = next((g for g in m.groups() if g), "anonymous")
                params_str = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
                params = [p.strip() for p in params_str.split(",") if p.strip()]
                functions.append(FunctionInfo(name=name, start_line=i + 1, end_line=i + 1, parameters=params))

        # Count structural keywords as loop/condition proxies
        loop_keywords = re.compile(r"\b(for|while)\b")
        cond_keywords = re.compile(r"\b(if|elif|else)\b")

        loop_count = sum(len(loop_keywords.findall(l)) for l in lines)
        conditional_count = sum(len(cond_keywords.findall(l)) for l in lines)

        # Estimate loop depth by leading indentation changes around loops
        max_depth = _estimate_max_loop_depth_regex(code)

        # Detect recursion heuristically: function name appears in its own body
        has_recursion = False
        for fn in functions:
            fn_body = "\n".join(lines)
            if fn.name in fn_body:
                count = fn_body.count(fn.name)
                if count > 1:  # More than just the definition
                    has_recursion = True
                    fn.is_recursive = True

        return ASTSummary(
            functions=functions,
            loop_count=loop_count,
            max_loop_depth=max_depth,
            conditional_count=conditional_count,
            has_recursion=has_recursion,
            language=lang_config.language_id if lang_config else "unknown",
            node_count=len(lines),
        )


# ── Tree-sitter AST Walker ────────────────────────────────────────────────────

class _ASTWalker:
    """
    Single-pass recursive visitor over a Tree-sitter parse tree.
    Accumulates structural metrics used by the complexity analyzer.
    """

    def __init__(self, lang_config: LanguageConfig, source: str):
        self._lang = lang_config
        self._source = source.encode("utf-8")
        self.functions: list[FunctionInfo] = []
        self.loop_count: int = 0
        self.max_loop_depth: int = 0
        self.conditional_count: int = 0
        self.has_recursion: bool = False
        self.node_count: int = 0
        self._current_depth: int = 0
        self._function_names: set[str] = set()

    def walk(self, node, loop_depth: int = 0):
        self.node_count += 1
        node_type = node.type

        # Track loops and their depth
        if node_type in self._lang.loop_node_types:
            self.loop_count += 1
            loop_depth += 1
            self.max_loop_depth = max(self.max_loop_depth, loop_depth)

        # Track conditionals
        if node_type in self._lang.conditional_node_types:
            self.conditional_count += 1

        # Extract function definitions
        if node_type in self._lang.function_node_types:
            fn_info = self._extract_function_info(node)
            if fn_info:
                self.functions.append(fn_info)
                self._function_names.add(fn_info.name)

        # Detect call sites for recursion
        if node_type in self._lang.call_node_types:
            callee = self._get_callee_name(node)
            if callee and callee in self._function_names:
                self.has_recursion = True
                # Mark the function as recursive
                for fn in self.functions:
                    if fn.name == callee:
                        fn.is_recursive = True

        # Recurse into children
        for child in node.children:
            self.walk(child, loop_depth)

    def _extract_function_info(self, node) -> Optional[FunctionInfo]:
        name_node = node.child_by_field_name("name")
        params_node = node.child_by_field_name("parameters")

        name = name_node.text.decode("utf-8") if name_node else "anonymous"
        params: list[str] = []

        if params_node:
            for child in params_node.children:
                if child.type == "identifier":
                    params.append(child.text.decode("utf-8"))

        return FunctionInfo(
            name=name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            parameters=params,
        )

    def _get_callee_name(self, node) -> Optional[str]:
        """Extract the name of the function being called from a call node."""
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return None
        if func_node.type == "identifier":
            return func_node.text.decode("utf-8")
        # Handle method calls like obj.method() — check child named "attribute"
        attr = func_node.child_by_field_name("attribute")
        if attr:
            return attr.text.decode("utf-8")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _estimate_max_loop_depth_regex(code: str) -> int:
    """
    Estimate the max nesting depth of loops by tracking indentation.
    This is a rough heuristic for when tree-sitter is unavailable.
    """
    loop_re = re.compile(r"^(\s*)(for|while)\b")
    indent_stack: list[int] = []
    max_depth = 0

    for line in code.splitlines():
        m = loop_re.match(line)
        if m:
            indent = len(m.group(1))
            # Pop stack while current indent is shallower
            while indent_stack and indent_stack[-1] >= indent:
                indent_stack.pop()
            indent_stack.append(indent)
            max_depth = max(max_depth, len(indent_stack))

    return max_depth
