/**
 * analysisService.ts — Extension Analysis Service
 * -------------------------------------------------
 * Sits between VS Code commands and the BackendClient, mirroring the
 * service-layer pattern used in the Python backend.
 *
 * Responsibilities:
 *   - Input validation before hitting the network
 *   - Normalizing VS Code language IDs to backend-compatible strings
 *   - Caching recent results by code fingerprint (avoids redundant API calls
 *     when the user re-analyzes the same selection)
 *   - Logging / telemetry hooks (future-ready)
 *
 * Commands import this service, NOT BackendClient directly. This decoupling
 * means we can add caching, retries, or offline mode without touching command code.
 */

import * as vscode from 'vscode';
import { BackendClient } from '../api/backendClient';
import type { AnalysisResult, FileSummaryResult } from '../types/analysis';


const _outputChannel = vscode.window.createOutputChannel('AI Code Intelligence');
/** Maximum code length we'll send to the backend (soft guard). */
const MAX_CODE_LENGTH = 50_000;

/** Simple in-memory LRU cache keyed by a code fingerprint. */
const _resultCache = new Map<string, { result: AnalysisResult; timestamp: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// VS Code languageId → backend language string normalization table
const LANGUAGE_ALIASES: Record<string, string> = {
    javascriptreact: 'javascript',
    typescriptreact: 'typescript',
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
};

export class AnalysisService {
    private readonly _client: BackendClient;

    constructor(client: BackendClient) {
        this._client = client;
    }

    // ── Public API ─────────────────────────────────────────────────────────────

    /**
     * Analyze a code snippet, using a cache if the same snippet was recently analyzed.
     * Throws a user-friendly Error on validation failures.
     */
    async analyzeSnippet(
        code: string,
        languageId: string,
        filePath?: string
    ): Promise<AnalysisResult> {
        const language = this._normalizeLanguage(languageId);

        // ── Validation ──────────────────────────────────────────────────────────
        if (!code.trim()) {
            throw new Error('Selected code is empty. Please select a non-empty snippet.');
        }
        if (code.length > MAX_CODE_LENGTH) {
            throw new Error(
                `Selection is too large (${code.length} chars). Please select a smaller snippet (max ${MAX_CODE_LENGTH} chars).`
            );
        }

        // ── Cache lookup ────────────────────────────────────────────────────────
        const cacheKey = this._fingerprint(code, language);
        const cached = _resultCache.get(cacheKey);
        if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
            // Cache hit — log to extension output channel (no console in strict tsconfig target)
            _outputChannel.appendLine(`[AnalysisService] Cache hit for ${cacheKey}`);

            return cached.result;
        }

        // ── Network call ─────────────────────────────────────────────────────────
        _outputChannel.appendLine(`[Cache] Miss - fetching from backend for key: ${cacheKey}`);
        const result = await this._client.analyze({ code, language, file_path: filePath });

        // Cache the result
        _resultCache.set(cacheKey, { result, timestamp: Date.now() });
        this._evictStaleCache();

        return result;
    }

    /**
     * Summarize a full file's content.
     */
    async summarizeFile(
        content: string,
        languageId: string,
        filePath?: string
    ): Promise<FileSummaryResult> {
        const language = this._normalizeLanguage(languageId);

        if (!content.trim()) {
            throw new Error('File is empty — nothing to summarize.');
        }

        return this._client.summarizeFile({ content, language, file_path: filePath });
    }

    /**
     * Probe the backend and return a status string for display.
     * Never throws — returns an error description instead.
     */
    async getBackendStatus(): Promise<{ online: boolean; provider: string; message: string }> {
        try {
            const health = await this._client.healthCheck();
            return {
                online: true,
                provider: health.llm_provider,
                message: `Backend ready · LLM: ${health.llm_provider}`,
            };
        } catch (err: unknown) {
            return {
                online: false,
                provider: 'unknown',
                message: err instanceof Error ? err.message : 'Backend unreachable',
            };
        }
    }

    /**
     * Invalidate the cache — useful after the user changes the backend URL setting.
     */
    clearCache(): void {
        _resultCache.clear();
    }

    // ── Private helpers ────────────────────────────────────────────────────────

    private _normalizeLanguage(languageId: string): string {
        return LANGUAGE_ALIASES[languageId.toLowerCase()] ?? languageId.toLowerCase();
    }

    private _fingerprint(code: string, language: string): string {
        // Simple non-cryptographic hash for cache keying
        let h = 5381;
        const str = language + ':' + code;
        for (let i = 0; i < str.length; i++) {
            h = ((h << 5) + h + str.charCodeAt(i)) >>> 0;
        }
        return h.toString(16);
    }

    private _evictStaleCache(): void {
        const now = Date.now();
        for (const [key, entry] of _resultCache) {
            if (now - entry.timestamp > CACHE_TTL_MS) {
                _resultCache.delete(key);
            }
        }
        // Hard cap to prevent unbounded growth
        if (_resultCache.size > 50) {
            const oldest = [..._resultCache.entries()].sort((a, b) => a[1].timestamp - b[1].timestamp);
            oldest.slice(0, 10).forEach(([k]) => _resultCache.delete(k));
        }
    }
}
