/**
 * extension.ts — VS Code Extension Activation Entrypoint
 * ---------------------------------------------------------
 * Instantiates shared services and registers all commands.
 * Commands receive AnalysisService (not BackendClient directly).
 */

import * as vscode from 'vscode';
import { BackendClient } from './api/backendClient';
import { AnalysisService } from './services/analysisService';
import { analyzeFunctionCommand, summarizeFileCommand } from './commands/analyzeFunction';

export function activate(context: vscode.ExtensionContext): void {
    const client = new BackendClient();
    const service = new AnalysisService(client);
    const { extensionUri } = context;

    // ── Background health check ───────────────────────────────────────────────
    service.getBackendStatus().then(({ message }) => {
        vscode.window.setStatusBarMessage(`AI Code Intel: ${message}`, 6000);
    });

    // ── Register commands ─────────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand(
            'aiCodeIntel.analyzeFunction',
            () => analyzeFunctionCommand(extensionUri, service)
        ),
        vscode.commands.registerCommand(
            'aiCodeIntel.summarizeFile',
            () => summarizeFileCommand(extensionUri, service)
        ),
        // Clear cache when the user changes the backend URL setting
        vscode.workspace.onDidChangeConfiguration((e: vscode.ConfigurationChangeEvent) => {
            if (e.affectsConfiguration('aiCodeIntel.backendUrl')) {
                service.clearCache();
                vscode.window.setStatusBarMessage('AI Code Intel: cache cleared after URL change', 3000);
            }
        }),
    );
}

export function deactivate(): void {
    // VS Code disposes subscriptions registered in context.subscriptions automatically.
}
