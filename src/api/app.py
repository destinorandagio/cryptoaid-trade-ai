"""FastAPI Application Entrypoint for CryptoAID Trade AI."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes.v1 import router as v1_router
from src.config import settings
from src.learning.auto_learner import global_auto_learner as auto_learner

PWA_DIR = Path(__file__).resolve().parent.parent / "pwa"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start H24 Auto-Learning Engine
    await auto_learner.start()
    yield
    # Shutdown: Stop Auto-Learning Engine
    await auto_learner.stop()


app = FastAPI(
    title="CryptoAID Trade AI",
    version=settings.app_version,
    description="AI Trading + Web3 Intelligence + Risk Intelligence + Multi-Agent Decision Engine",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# Enable CORS for local PWA testing and frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 REST API
app.include_router(v1_router)

# Mount PWA static assets
if PWA_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(PWA_DIR)), name="static")


@app.get("/")
def serve_pwa_root():
    """Serve PWA index page."""
    index_file = PWA_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "status": "ONLINE",
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": "/api/v1",
    }
