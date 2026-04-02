"""
prompts.py — LLM Prompt Templates
-----------------------------------
Centralizing prompts here keeps them versioned, testable, and easy to iterate on
independently of the LLM client or business logic. Each function returns a
system/user message pair ready for use with the OpenAI or Anthropic chat API.

Design note: we embed the AST summary and complexity estimate directly into prompts
so the LLM reasons from structured facts rather than re-inferring them from raw code.
This improves accuracy and reduces token usage.
"""

from __future__ import annotations
from api.models.schemas import ASTSummary, ComplexityInfo


def build_documentation_prompt(
    code: str,
    language: str,
    ast_summary: ASTSummary,
    complexity: ComplexityInfo,
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for documentation generation.
    The output should be a ready-to-paste docstring/JSDoc comment.
    """
    fn_names = [f.name for f in ast_summary.functions] or ["(no named functions detected)"]
    comment_style = "Python docstrings (\"\"\"...\"\"\")" if language == "python" else "JSDoc (/** ... */)"

    system = (
        "You are a senior software engineer who writes clear, precise technical documentation. "
        "Generate documentation in the appropriate format for the language. "
        "Be concise but complete. Never invent functionality that doesn't exist in the code."
    )

    user = f"""Generate a {comment_style} comment for the following {language} code.

The AST analysis found:
- Functions/methods: {', '.join(fn_names)}
- Loop count: {ast_summary.loop_count}
- Has recursion: {ast_summary.has_recursion}
- Estimated complexity: {complexity.estimate}

Include these sections:
1. @description — one-sentence summary of purpose
2. @param — each parameter with type and description
3. @returns — return value description
4. @complexity — the Big-O estimate with a brief explanation
5. @example — a simple usage example

Code:
```{language}
{code}
```

Return ONLY the comment block, no surrounding text."""

    return system, user


def build_explanation_prompt(code: str, language: str, ast_summary: ASTSummary) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for plain-English algorithm explanation.
    """
    system = (
        "You are an expert software engineer and technical writer. "
        "Explain code to an intelligent developer who may not be familiar with this specific algorithm. "
        "Be precise, clear, and structured. Use numbered steps for sequential logic."
    )

    fn_count = len(ast_summary.functions)
    recursion_hint = "The code uses recursion." if ast_summary.has_recursion else ""

    user = f"""Explain what the following {language} code does in plain English.

Context from AST analysis:
- Detected {fn_count} function(s): {', '.join(f.name for f in ast_summary.functions) or 'none'}
- Loop depth: {ast_summary.max_loop_depth}
- {recursion_hint}

Provide:
1. **Overview** (1-2 sentences): What is the high-level purpose?
2. **Step-by-step walkthrough**: What does the code do, step by step?
3. **Edge cases or gotchas** (if any): Anything a developer should watch out for?

Code:
```{language}
{code}
```

Write in clear, concise prose. Do not repeat the code."""

    return system, user


def build_summarization_prompt(file_content: str, language: str) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) for full-file summarization / README generation.
    """
    system = (
        "You are a senior engineer creating a project summary for a README. "
        "Be informative and developer-friendly. Avoid corporate jargon."
    )

    user = f"""Analyze this {language} source file and produce:

1. **File Summary** (2-3 sentences): What does this file do? What is its role in a larger system?
2. **Key Exports / Public API**: List the main functions, classes, or constants that other modules would use.
3. **Suggested README Section**: Write a short README-ready markdown section a developer could use to document this module.

File content:
```{language}
{file_content[:4000]}  
```
{"[Content truncated for length]" if len(file_content) > 4000 else ""}

Return structured markdown."""

    return system, user
