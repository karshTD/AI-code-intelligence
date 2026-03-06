/**
 * analyzeFunction.ts — "Analyze Selected Code" Command
 * ------------------------------------------------------
 * Commands delegate to AnalysisService (not BackendClient directly).
 * AnalysisService handles caching, input normalization, and validation
 * before hitting the network — commands stay focused on VS Code UX.
 */

import * as vscode from 'vscode';
import { AnalysisService } from '../services/analysisService';
import { ResultsPanel } from '../ui/resultsPanel';

export async function analyzeFunctionCommand(
    extensionUri: vscode.Uri,
    service: AnalysisService
): Promise<void> {
    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showWarningMessage('AI Code Intelligence: No active editor.');
        return;
    }

    const selection = editor.selection;
    if (selection.isEmpty) {
        vscode.window.showWarningMessage(
            'AI Code Intelligence: Please select a code snippet to analyze.'
        );
        return;
    }

    const code = editor.document.getText(selection);
    const languageId = editor.document.languageId;
    const filePath = editor.document.fileName;

    const panel = ResultsPanel.show(extensionUri, null, `Analyzing ${languageId} code…`);
    panel.showLoading(`Sending ${languageId} snippet to AI backend…`);

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'AI Code Intelligence',
            cancellable: false,
        },
        async (progress: vscode.Progress<{ message?: string; increment?: number }>) => {
            progress.report({ message: 'Parsing AST and estimating complexity…' });
            try {
                const result = await service.analyzeSnippet(code, languageId, filePath);
                progress.report({ message: 'Rendering results…', increment: 100 });
                panel.render(result);
            } catch (err: unknown) {
                const message = err instanceof Error ? err.message : String(err);
                panel.showError(message);
                vscode.window.showErrorMessage(`Analysis failed: ${message}`);
            }
        }
    );
}

export async function summarizeFileCommand(
    extensionUri: vscode.Uri,
    service: AnalysisService
): Promise<void> {
    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showWarningMessage('AI Code Intelligence: No active editor.');
        return;
    }

    const content = editor.document.getText();
    const languageId = editor.document.languageId;
    const filePath = editor.document.fileName;

    if (!content.trim()) {
        vscode.window.showWarningMessage('AI Code Intelligence: The active file is empty.');
        return;
    }

    const panel = ResultsPanel.show(extensionUri, null, 'Summarizing file…');
    panel.showLoading('Sending file to AI backend for summarization…');

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: 'AI Code Intelligence',
            cancellable: false,
        },
        async (progress: vscode.Progress<{ message?: string; increment?: number }>) => {
            progress.report({ message: 'Generating file summary…' });
            try {
                const result = await service.summarizeFile(content, languageId, filePath);
                progress.report({ message: 'Rendering results…', increment: 100 });
                panel.render(result);
            } catch (err: unknown) {
                const message = err instanceof Error ? err.message : String(err);
                panel.showError(message);
                vscode.window.showErrorMessage(`Summarization failed: ${message}`);
            }
        }
    );
}
