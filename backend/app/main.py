"""
FastAPI application entry point.

Registers routes, sets up CORS, and loads the .env file.
Run with:  cd backend && python3 -m uvicorn app.main:app --reload
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load .env from the project root (two levels above this file)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from app.core.config import AuthSettings, get_auth_settings  # noqa: E402
from app.routers import (  # noqa: E402
    ai_assistant,
    activation,
    auth,
    instructor_courses,
    instructor_enrollments,
    instructor_roster,
    simulate,
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

    api.include_router(ai_assistant.router)
    api.include_router(simulate.router)
    api.include_router(auth.router, prefix="/api")
    # Vite strips the browser-facing /api prefix before proxying locally.
    api.include_router(auth.router, include_in_schema=False)
    api.include_router(activation.router, prefix="/api")
    api.include_router(activation.router, include_in_schema=False)
    api.include_router(instructor_courses.router, prefix="/api")
    api.include_router(instructor_courses.router, include_in_schema=False)
    api.include_router(instructor_roster.router, prefix="/api")
    api.include_router(instructor_roster.router, include_in_schema=False)
    api.include_router(instructor_enrollments.router, prefix="/api")
    api.include_router(instructor_enrollments.router, include_in_schema=False)

    @api.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return api


app = create_app()
