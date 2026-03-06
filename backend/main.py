"""
main.py — FastAPI Application Entrypoint
------------------------------------------
This file is intentionally minimal. Its only job is:
  - Create the FastAPI app instance
  - Configure middleware (CORS for VS Code extension → localhost)
  - Mount routers
  - Define the /health endpoint

Business logic lives exclusively in api/routes/, analysis/, and ai/.
Keeping main.py thin makes it easy to add additional routers or middleware later
without touching any domain code.
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from api.routes.analysis import router as analysis_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App factory ───────────────────────────────────────────────────────────────
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-powered code analysis backend. Accepts code snippets, performs AST parsing, "
        "estimates complexity, and generates documentation and explanations using an LLM."
    ),
    docs_url="/docs",    # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc UI at http://localhost:8000/redoc
)

# ── Middleware ────────────────────────────────────────────────────────────────
# CORS is required so the VS Code WebView (origin: vscode-webview://) and any
# local browser dev tools can reach this API without CORS errors.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(analysis_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["infrastructure"], summary="Health check")
async def health():
    """
    Simple liveness probe. Returns the active LLM provider so callers can
    confirm which AI backend is configured without needing to attempt a real call.
    """
    from api.models.schemas import HealthResponse
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        llm_provider=settings.effective_provider,
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"message": f"Welcome to {settings.app_name} v{settings.app_version}. See /docs for the API."}


# ── Dev server entry ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting %s v%s on port %d", settings.app_name, settings.app_version, settings.port)
    logger.info("Active LLM provider: %s", settings.effective_provider)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
