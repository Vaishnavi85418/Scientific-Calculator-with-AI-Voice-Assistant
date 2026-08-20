"""
FastAPI application entry point.

Run with:
    uvicorn main:app --reload

Docs available at:
    http://127.0.0.1:8000/docs   (Swagger UI)
    http://127.0.0.1:8000/redoc  (ReDoc)
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import close_connection, ping_database
from routes.calculator import router as calculator_router
from routes.voice import router as voice_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Load .env before anything else
load_dotenv()


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown logic
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("Starting SciCalc API…")
    if ping_database():
        logger.info("MongoDB connection: OK")
    else:
        logger.warning(
            "MongoDB is not reachable. History features will be unavailable."
        )
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutting down — closing MongoDB connection.")
    close_connection()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SciCalc API",
    description=(
        "REST API for the SciCalc Scientific Calculator. "
        "Provides expression evaluation and persistent calculation history."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# During local development the frontend is served from file:// or a local
# dev server (e.g. Live Server on port 5500).  Add or adjust origins as needed.
# In production, replace with your actual frontend domain.
ALLOWED_ORIGINS: list[str] = [
    "http://localhost:5500",        # VS Code Live Server default
    "http://127.0.0.1:5500",
    "http://localhost:3000",        # common React / Vite dev server
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "null",                         # file:// origin (browser sends "null")
]

# Allow extra origins from .env  (comma-separated)
extra = os.getenv("EXTRA_CORS_ORIGINS", "")
if extra:
    ALLOWED_ORIGINS.extend([o.strip() for o in extra.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(calculator_router)
app.include_router(voice_router)


# ---------------------------------------------------------------------------
# Root health-check
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"], summary="Health check")
async def root():
    """Quick health check — also confirms the API is reachable."""
    db_ok = ping_database()
    return JSONResponse(
        content={
            "status": "ok",
            "service": "SciCalc API",
            "version": "1.0.0",
            "database": "connected" if db_ok else "unavailable",
        }
    )


@app.get("/health", tags=["health"], summary="Detailed health")
async def health():
    db_ok = ping_database()
    return {
        "api": "ok",
        "database": "ok" if db_ok else "unavailable",
    }
