/**
 * backendClient.ts — HTTP Client for the Analysis Backend
 * ---------------------------------------------------------
 * Encapsulates all network communication with the FastAPI backend.
 * Using Node's built-in `http`/`https` modules avoids adding a dependency
 * (like axios) to the extension bundle. VS Code extensions should be lean.
 *
 * Design: The base URL is read from VS Code workspace configuration so users
 * can point the extension at a remote or Docker-hosted backend if needed.
 */

import * as http from 'http';
import * as https from 'https';
import * as vscode from 'vscode';
import type {
    AnalysisRequest,
    AnalysisResult,
    FileSummaryRequest,
    FileSummaryResult,
} from '../types/analysis';

export class BackendClient {
    private get baseUrl(): string {
        return vscode.workspace
            .getConfiguration('aiCodeIntel')
            .get<string>('backendUrl', 'http://localhost:8000');
    }

    private get timeoutMs(): number {
        return vscode.workspace
            .getConfiguration('aiCodeIntel')
            .get<number>('requestTimeoutMs', 30000);
    }

    /** POST /api/v1/analyze — analyze a code snippet */
    async analyze(request: AnalysisRequest): Promise<AnalysisResult> {
        return this.post<AnalysisResult>('/api/v1/analyze', request);
    }

    /** POST /api/v1/summarize — summarize a full file */
    async summarizeFile(request: FileSummaryRequest): Promise<FileSummaryResult> {
        return this.post<FileSummaryResult>('/api/v1/summarize', request);
    }

    /** GET /health — check server status */
    async healthCheck(): Promise<{ status: string; llm_provider: string }> {
        return this.get('/health');
    }

    // ── Private HTTP helpers ──────────────────────────────────────────────────

    private async post<T>(path: string, body: unknown): Promise<T> {
        const url = new URL(path, this.baseUrl);
        const payload = JSON.stringify(body);

        return new Promise((resolve, reject) => {
            const lib = url.protocol === 'https:' ? https : http;
            const options: http.RequestOptions = {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(payload),
                },
                timeout: this.timeoutMs,
            };

            const req = lib.request(url, options, (res) => {
                this.collectResponseBody(res).then((raw) => {
                    if (res.statusCode && res.statusCode >= 400) {
                        reject(new Error(`Backend error ${res.statusCode}: ${raw}`));
                        return;
                    }
                    try {
                        resolve(JSON.parse(raw) as T);
                    } catch {
                        reject(new Error(`Invalid JSON response: ${raw.slice(0, 200)}`));
                    }
                });
            });

            req.on('timeout', () => {
                req.destroy();
                reject(new Error(`Request timed out after ${this.timeoutMs}ms. Is the backend running at ${this.baseUrl}?`));
            });

            req.on('error', (err) => {
                reject(new Error(`Cannot reach backend at ${this.baseUrl}: ${err.message}`));
            });

            req.write(payload);
            req.end();
        });
    }

    private async get<T>(path: string): Promise<T> {
        const url = new URL(path, this.baseUrl);

        return new Promise((resolve, reject) => {
            const lib = url.protocol === 'https:' ? https : http;
            const req = lib.get(url, { timeout: this.timeoutMs }, (res) => {
                this.collectResponseBody(res).then((raw) => {
                    try {
                        resolve(JSON.parse(raw) as T);
                    } catch {
                        reject(new Error(`Invalid JSON: ${raw.slice(0, 200)}`));
                    }
                });
            });
            req.on('error', reject);
        });
    }

    private collectResponseBody(res: http.IncomingMessage): Promise<string> {
        return new Promise((resolve) => {
            const chunks: Buffer[] = [];
            res.on('data', (chunk: Buffer) => chunks.push(chunk));
            res.on('end', () => resolve(Buffer.concat(chunks).toString('utf-8')));
        });
    }
}
