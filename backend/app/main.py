"""
FastAPI application entry point.

Registers routes, sets up CORS, and loads the .env file.
Run with:  cd backend && python3 -m uvicorn app.main:app --reload
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from the project root (two levels above this file)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from app.routers import ai_assistant  # noqa: E402 — import after dotenv load

app = FastAPI(
    title="Resource Allocation Simulator API",
    version="0.1.0",
)

# Allow the Vite dev server (5173) and preview server (4173).
# Override with CORS_ALLOW_ORIGINS env var for deployment.
_default_origins = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:4173,http://127.0.0.1:4173"
)
_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOW_ORIGINS", _default_origins).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_assistant.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
