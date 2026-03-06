/**
 * resultsPanel.ts — WebView Results Panel
 * -----------------------------------------
 * Manages a singleton VS Code WebView panel that renders AnalysisResult data.
 *
 * Singleton pattern: only one panel exists at a time. Showing a new result on
 * an existing panel (reveal) is cheaper than creating a new panel and avoids
 * cluttering the editor with tabs.
 *
 * Security note: all dynamic content is HTML-escaped before injection into the
 * WebView to prevent XSS from malicious code snippets triggering script injection.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import type { AnalysisResult, FileSummaryResult } from '../types/analysis';

export class ResultsPanel {
    public static readonly viewType = 'aiCodeIntel.results';
    private static _instance: ResultsPanel | undefined;

    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;

    // ── Singleton factory ─────────────────────────────────────────────────────

    public static show(
        extensionUri: vscode.Uri,
        result: AnalysisResult | FileSummaryResult | null,
        title: string = 'AI Code Analysis'
    ): ResultsPanel {
        const column = vscode.window.activeTextEditor
            ? vscode.ViewColumn.Beside
            : vscode.ViewColumn.One;

        if (ResultsPanel._instance) {
            ResultsPanel._instance._panel.reveal(column);
        } else {
            const panel = vscode.window.createWebviewPanel(
                ResultsPanel.viewType,
                title,
                column,
                {
                    enableScripts: true,
                    // Restrict local resource loading to the extension's webview directory
                    localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'src', 'ui', 'webview')],
                }
            );
            ResultsPanel._instance = new ResultsPanel(panel, extensionUri);
        }

        if (result) {
            ResultsPanel._instance.render(result);
        }

        return ResultsPanel._instance;
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        this._panel.onDidDispose(() => {
            ResultsPanel._instance = undefined;
        });
    }

    // ── Rendering ─────────────────────────────────────────────────────────────

    public showLoading(message: string = 'Analyzing code…') {
        this._panel.webview.html = this._buildLoadingHtml(message);
    }

    public showError(message: string) {
        this._panel.webview.html = this._buildErrorHtml(message);
    }

    public render(result: AnalysisResult | FileSummaryResult) {
        if ('complexity' in result) {
            this._panel.webview.html = this._buildAnalysisHtml(result);
        } else {
            this._panel.webview.html = this._buildSummaryHtml(result);
        }
    }

    // ── HTML builders ─────────────────────────────────────────────────────────

    private _buildAnalysisHtml(r: AnalysisResult): string {
        const esc = ResultsPanel._escape;

        const fns = r.ast_summary.functions
            .map(f =>
                `<tr>
          <td class="fn-name">${esc(f.name)}</td>
          <td>${esc(f.parameters.join(', ') || '—')}</td>
          <td>${f.is_recursive ? '<span class="badge badge-warn">recursive</span>' : '—'}</td>
          <td>L${f.start_line}–${f.end_line}</td>
        </tr>`
            ).join('') || '<tr><td colspan="4">No functions detected</td></tr>';

        const confidenceClass = {
            high: 'badge-success',
            medium: 'badge-warn',
            low: 'badge-info',
        }[r.complexity.confidence] ?? 'badge-info';

        const template = this._loadTemplate();
        return template
            .replace('{{TITLE}}', 'Code Analysis')
            .replace('{{BODY}}', `
        <section class="card">
          <h2>📊 Complexity</h2>
          <div class="complexity-row">
            <span class="complexity-badge">${esc(r.complexity.estimate)}</span>
            <span class="badge ${confidenceClass}">confidence: ${esc(r.complexity.confidence)}</span>
          </div>
          <p class="reasoning">${esc(r.complexity.reasoning)}</p>
        </section>

        <section class="card">
          <h2>📝 Documentation</h2>
          <pre class="code-block">${esc(r.documentation)}</pre>
        </section>

        <section class="card">
          <h2>💡 Explanation</h2>
          <div class="explanation">${this._markdownToHtml(r.explanation)}</div>
        </section>

        <section class="card">
          <h2>🌳 AST Summary</h2>
          <div class="stats-grid">
            <div class="stat"><span class="stat-val">${r.ast_summary.loop_count}</span><span class="stat-lbl">Loops</span></div>
            <div class="stat"><span class="stat-val">${r.ast_summary.max_loop_depth}</span><span class="stat-lbl">Max Depth</span></div>
            <div class="stat"><span class="stat-val">${r.ast_summary.conditional_count}</span><span class="stat-lbl">Conditionals</span></div>
            <div class="stat"><span class="stat-val">${r.ast_summary.has_recursion ? '✓' : '✗'}</span><span class="stat-lbl">Recursion</span></div>
          </div>
          <h3>Detected Functions</h3>
          <table class="fn-table">
            <thead><tr><th>Name</th><th>Parameters</th><th>Flags</th><th>Lines</th></tr></thead>
            <tbody>${fns}</tbody>
          </table>
        </section>

        <footer class="provider-info">Powered by ${esc(r.provider_used)}</footer>
      `);
    }

    private _buildSummaryHtml(r: FileSummaryResult): string {
        const esc = ResultsPanel._escape;
        const template = this._loadTemplate();
        const exports = r.detected_exports
            .map(e => `<li><code>${esc(e)}</code></li>`)
            .join('') || '<li>None detected</li>';

        return template
            .replace('{{TITLE}}', 'File Summary')
            .replace('{{BODY}}', `
        <section class="card">
          <h2>📄 File Summary</h2>
          <div class="explanation">${this._markdownToHtml(r.summary)}</div>
        </section>
        <section class="card">
          <h2>📦 Detected Exports</h2>
          <ul class="export-list">${exports}</ul>
        </section>
        <section class="card">
          <h2>📖 Suggested README</h2>
          <pre class="code-block">${esc(r.suggested_readme)}</pre>
        </section>
        <footer class="provider-info">Powered by ${esc(r.provider_used)}</footer>
      `);
    }

    private _buildLoadingHtml(message: string): string {
        return `<!DOCTYPE html><html><body style="background:#1e1e2e;color:#cdd6f4;font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;gap:12px;">
      <div class="spinner"></div><p>${ResultsPanel._escape(message)}</p>
      <style>.spinner{width:20px;height:20px;border:3px solid #313244;border-top-color:#89b4fa;border-radius:50%;animation:spin 0.8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}</style>
    </body></html>`;
    }

    private _buildErrorHtml(message: string): string {
        return `<!DOCTYPE html><html><body style="background:#1e1e2e;color:#f38ba8;font-family:system-ui;padding:2rem;">
      <h2>⚠️ Error</h2><p>${ResultsPanel._escape(message)}</p>
      <p style="color:#6c7086;font-size:0.85em">Make sure the backend is running: <code>uvicorn main:app --reload</code></p>
    </body></html>`;
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private _loadTemplate(): string {
        const templatePath = path.join(
            this._extensionUri.fsPath,
            'src', 'ui', 'webview', 'panel.html'
        );
        try {
            return fs.readFileSync(templatePath, 'utf-8');
        } catch {
            // Inline fallback if template file can't be read
            return '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>{{BODY}}</body></html>';
        }
    }

    private _markdownToHtml(md: string): string {
        // Minimal markdown → HTML: bold, code, headings, lists
        return ResultsPanel._escape(md)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/^#{1,3}\s+(.+)$/gm, '<h3>$1</h3>')
            .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
            .replace(/^-\s+(.+)$/gm, '<li>$1</li>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }

    private static _escape(str: string): string {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }
}
