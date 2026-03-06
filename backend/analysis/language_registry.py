"""
language_registry.py — Multi-Language Parser Registry
-------------------------------------------------------
Architectural decision: we use a registry pattern so that adding support for a
new language only requires installing its tree-sitter grammar and adding one
entry here. Routes and parser code stay unchanged.

Supported languages initially: Python, JavaScript, TypeScript.
All other languages fall through to a 'generic' fallback that still extracts
basic metrics (line count, brace depth) without a full parse tree.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LanguageConfig:
    """
    Configuration for a supported language.

    tree_sitter_module: the importable tree-sitter language package name.
    comment_style:      how documentation comments are formatted in this language.
    function_node_types: Tree-sitter node type names that represent function definitions.
    loop_node_types:     node types for loop constructs.
    """
    language_id: str
    display_name: str
    tree_sitter_module: str
    comment_style: str  # "hash", "slash", "docstring"
    function_node_types: list[str] = field(default_factory=list)
    loop_node_types: list[str] = field(default_factory=list)
    conditional_node_types: list[str] = field(default_factory=list)
    call_node_types: list[str] = field(default_factory=list)


# ── Registry Definition ───────────────────────────────────────────────────────
# Each entry maps a VS Code languageId → LanguageConfig.
# To add a new language: install `tree-sitter-<lang>` and add an entry below.

_REGISTRY: dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        language_id="python",
        display_name="Python",
        tree_sitter_module="tree_sitter_python",
        comment_style="docstring",
        function_node_types=["function_definition", "async_function_definition"],
        loop_node_types=["for_statement", "while_statement"],
        conditional_node_types=["if_statement", "elif_clause"],
        call_node_types=["call"],
    ),
    "javascript": LanguageConfig(
        language_id="javascript",
        display_name="JavaScript",
        tree_sitter_module="tree_sitter_javascript",
        comment_style="slash",
        function_node_types=[
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        ],
        loop_node_types=["for_statement", "while_statement", "do_statement", "for_in_statement", "for_of_statement"],
        conditional_node_types=["if_statement"],
        call_node_types=["call_expression"],
    ),
    "typescript": LanguageConfig(
        language_id="typescript",
        display_name="TypeScript",
        tree_sitter_module="tree_sitter_typescript",
        comment_style="slash",
        function_node_types=[
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
        ],
        loop_node_types=["for_statement", "while_statement", "do_statement", "for_in_statement", "for_of_statement"],
        conditional_node_types=["if_statement"],
        call_node_types=["call_expression"],
    ),
    "java": LanguageConfig(
        language_id="java",
        display_name="Java",
        tree_sitter_module="tree_sitter_java",
        comment_style="slash",
        function_node_types=["method_declaration", "constructor_declaration"],
        loop_node_types=["for_statement", "while_statement", "do_statement", "enhanced_for_statement"],
        conditional_node_types=["if_statement"],
        call_node_types=["method_invocation"],
    ),
}


class LanguageRegistry:
    """
    Provides O(1) lookup of language configurations.
    Returns None for unsupported languages so callers can decide on fallback behavior.
    """

    @staticmethod
    def get(language_id: str) -> Optional[LanguageConfig]:
        """Look up a language config by its VS Code languageId."""
        config = _REGISTRY.get(language_id.lower())
        if config is None:
            logger.warning("Language '%s' not in registry — will use generic fallback", language_id)
        return config

    @staticmethod
    def supported_languages() -> list[str]:
        """Return all registered language IDs."""
        return list(_REGISTRY.keys())

    @staticmethod
    def is_supported(language_id: str) -> bool:
        return language_id.lower() in _REGISTRY
