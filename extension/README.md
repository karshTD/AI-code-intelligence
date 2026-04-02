# AI Code Intelligence Platform

> A production-quality developer tool that analyzes code using AST parsing and AI to generate documentation, detect complexity, and explain algorithms — all inside VS Code.

## Architecture

```
VS Code Extension (TypeScript)
        │  HTTP POST /api/v1/analyze
        ▼
FastAPI Backend (Python)
        │
   ┌────▼─────────────────────────────────┐
   │  Language Registry                   │
   │  → AST Parser (Tree-sitter)          │
   │  → Complexity Analyzer               │
   │  → LLM Client (OpenAI / Anthropic)   │
   └──────────────────────────────────────┘
        │  AnalysisResult JSON
        ▼
WebView Results Panel (VS Code)
```

## Project Structure

```
ai-code-intelligence/
├── backend/          ← Python FastAPI server
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── api/
│   │   ├── routes/analysis.py   ← orchestration route
│   │   └── models/schemas.py    ← Pydantic models
│   ├── analysis/
│   │   ├── language_registry.py ← multi-language support
│   │   ├── ast_parser.py        ← Tree-sitter parser
│   │   └── complexity.py        ← Big-O estimator
│   └── ai/
│       ├── llm_client.py        ← OpenAI / Anthropic / Mock
│       └── prompts.py           ← prompt templates
└── extension/        ← VS Code extension (TypeScript)
    ├── package.json
    ├── tsconfig.json
    └── src/
        ├── extension.ts             ← activation entrypoint
        ├── types/analysis.ts        ← shared TypeScript types
        ├── commands/analyzeFunction.ts
        ├── api/backendClient.ts     ← HTTP client
        └── ui/
            ├── resultsPanel.ts      ← WebView manager
            └── webview/panel.html   ← results UI
```

## Quick Start

### 1. Backend

```powershell
cd backend

# Copy and configure environment
Copy-Item .env.example .env
# Edit .env → add your OPENAI_API_KEY or ANTHROPIC_API_KEY

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
# → Server starts at http://localhost:8000
# → Swagger docs at http://localhost:8000/docs
```

### 2. VS Code Extension

```powershell
cd extension

npm install
npm run compile

# Open the extension folder in VS Code and press F5 to launch
# a new Extension Development Host window.
```

### 3. Using the Extension

1. Open any `.py` or `.js` file in VS Code.
2. Select a function you want to analyze.
3. Right-click → **AI: Analyze Selected Code**  
   *(or run from the Command Palette: `Ctrl+Shift+P` → AI: Analyze)*
4. A results panel opens beside your editor showing:
   - 📊 Complexity estimate (Big-O with reasoning)
   - 📝 Auto-generated documentation
   - 💡 Plain-English explanation
   - 🌳 AST structural summary

## Configuration

| Setting | Default | Description |
|---|---|---|
| `aiCodeIntel.backendUrl` | `http://localhost:8000` | Backend server URL |
| `aiCodeIntel.requestTimeoutMs` | `30000` | Request timeout in ms |

Set in VS Code Settings (`Ctrl+,` → search "AI Code Intelligence").

## LLM Providers

| Provider | Config |
|---|---|
| OpenAI (default) | Set `OPENAI_API_KEY` in `backend/.env` |
| Anthropic Claude | Set `ANTHROPIC_API_KEY` and `LLM_PROVIDER=anthropic` |
| Mock (offline) | No key needed — produces realistic placeholder output |

## API Reference

```
POST /api/v1/analyze    ← analyze a code snippet
POST /api/v1/summarize  ← summarize a full file
GET  /health            ← server status + active LLM provider
GET  /docs              ← Swagger UI
```

## Adding a New Language

1. Install the grammar: `pip install tree-sitter-<lang>`
2. Add one entry to `backend/analysis/language_registry.py`
3. That's it — the parser, complexity analyzer, and routes require no changes.

## Future Improvements

- **Real-time inline hints** via VS Code `InlayHintsProvider`
- **Diff-mode analysis**: compare complexity before/after a refactor
- **Multi-file context**: send the full module graph to the LLM for cross-file explanations
- **Test generation**: use the AST summary to auto-generate unit test stubs
- **Git integration**: analyze changed functions on each commit
- **Language Server Protocol (LSP)**: migrate the backend to LSP for universal IDE support
