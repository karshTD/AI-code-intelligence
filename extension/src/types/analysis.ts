/**
 * analysis.ts — Shared TypeScript Types
 * ----------------------------------------
 * These interfaces mirror the Pydantic models in backend/api/models/schemas.py.
 * Keeping them in sync ensures the extension catches API contract violations
 * at compile time rather than at runtime.
 *
 * Naming convention: types use PascalCase; API field names use snake_case
 * to match the Python JSON response directly.
 */

export interface FunctionInfo {
    name: string;
    start_line: number;
    end_line: number;
    parameters: string[];
    is_recursive: boolean;
}

export interface ASTSummary {
    functions: FunctionInfo[];
    loop_count: number;
    max_loop_depth: number;
    conditional_count: number;
    has_recursion: boolean;
    language: string;
    node_count: number;
}

export interface ComplexityInfo {
    estimate: string;       // e.g. "O(n²)"
    reasoning: string;      // Human-readable explanation
    confidence: 'low' | 'medium' | 'high';
}

export interface AnalysisResult {
    documentation: string;
    complexity: ComplexityInfo;
    explanation: string;
    ast_summary: ASTSummary;
    provider_used: string;
}

export interface FileSummaryResult {
    summary: string;
    suggested_readme: string;
    detected_exports: string[];
    provider_used: string;
}

/** Payload sent to POST /api/v1/analyze */
export interface AnalysisRequest {
    code: string;
    language: string;
    file_path?: string;
    analyze_full_file?: boolean;
}

/** Payload sent to POST /api/v1/summarize */
export interface FileSummaryRequest {
    content: string;
    language: string;
    file_path?: string;
}
