"""
FastAPI application entry point.

Registers routes, sets up CORS, and loads the .env file.
Run with:  cd backend && python3 -m uvicorn app.main:app --reload
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Load .env from the project root (two levels above this file)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

# The built frontend (npm run build). Absent in local dev, where Vite's
# own dev server serves the frontend and proxies /api/* to this backend.
FRONTEND_DIST = PROJECT_ROOT / "dist"

from app.core.config import AuthSettings, get_auth_settings  # noqa: E402
from app.routers import (  # noqa: E402
    ai_assistant,
    activation,
    auth,
    instructor_courses,
    instructor_enrollments,
    instructor_progress,
    instructor_roster,
    simulate,
    submissions,
)


def create_app(auth_settings: AuthSettings | None = None) -> FastAPI:
    """Build the API with one explicit credentialed frontend origin."""

    settings = auth_settings or get_auth_settings()
    api = FastAPI(
        title="Resource Allocation Simulator API",
        version="0.1.0",
    )

    api.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.exception_handler(RequestValidationError)
    async def safe_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Return useful validation locations without echoing submitted secrets."""

        safe_errors = [
            {
                key: value
                for key, value in error.items()
                if key not in {"input", "ctx"}
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"detail": safe_errors},
        )

    api.include_router(ai_assistant.router, prefix="/api")
    api.include_router(simulate.router, prefix="/api")
    api.include_router(submissions.router, prefix="/api")
    api.include_router(auth.router, prefix="/api")
    api.include_router(activation.router, prefix="/api")
    api.include_router(instructor_courses.router, prefix="/api")
    api.include_router(instructor_roster.router, prefix="/api")
    api.include_router(instructor_enrollments.router, prefix="/api")
    api.include_router(instructor_progress.router, prefix="/api")

    if not settings.disable_legacy_proxy_routes:
        # Vite strips the browser-facing /api prefix before proxying
        # locally, so local dev needs these same routers reachable at
        # their bare (no "/api") paths too. In a single-origin production
        # deployment this must be disabled: these bare paths collide with
        # frontend SPA routes such as /instructor/courses.
        api.include_router(ai_assistant.router, include_in_schema=False)
        api.include_router(simulate.router, include_in_schema=False)
        api.include_router(submissions.router, include_in_schema=False)
        api.include_router(auth.router, include_in_schema=False)
        api.include_router(activation.router, include_in_schema=False)
        api.include_router(instructor_courses.router, include_in_schema=False)
        api.include_router(instructor_roster.router, include_in_schema=False)
        api.include_router(instructor_enrollments.router, include_in_schema=False)
        api.include_router(instructor_progress.router, include_in_schema=False)

    @api.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    # Production static frontend + SPA fallback. Only registered when a
    # build exists, so local dev (no dist/) is unaffected: Vite's dev
    # server keeps serving the frontend and proxying /api/* itself.
    if FRONTEND_DIST.is_dir():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            api.mount(
                "/assets",
                StaticFiles(directory=assets_dir),
                name="frontend-assets",
            )

        @api.get("/{full_path:path}", include_in_schema=False)
        def serve_frontend(full_path: str) -> FileResponse:
            """Serve a built static file, or fall back to index.html for
            client-side routes. Registered last, so every API route above
            still takes priority; only unmatched /api/* paths 404 here."""

            if full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return api


app = create_app()
