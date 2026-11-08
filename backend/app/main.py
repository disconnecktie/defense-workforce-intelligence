"""FastAPI application entry point for Defense Workforce Intelligence."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.postings import router as postings_router
from app.api.coverage import router as coverage_router

app = FastAPI(
    title="Defense Workforce Intelligence API",
    version="0.1.0",
    description="Source-attributed defense technology workforce analytics (in development).",
)

# Restrict browser clients to local development origins by default.
# A deployed environment must set DWI_CORS_ORIGINS explicitly.
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "DWI_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# This endpoint is explicitly opt-in and only selects synthetic test sources.
app.include_router(postings_router)
app.include_router(coverage_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness check; does not imply database readiness."""
    return {"status": "ok", "service": "dwi-api"}


@app.get("/api/v1/health", tags=["health"])
def versioned_health() -> dict[str, str]:
    """Versioned liveness check for future API consumers."""
    return health()
