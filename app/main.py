"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    AlreadyApprovedError,
    ApprovalLimitExceededError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    InvalidStateError,
    MMCoreError,
    NotFoundError,
    ValidationError,
)
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    setup_logging()
    settings = get_settings()
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
    )
    yield
    # Shutdown
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Core business logic service for Mattermost command center",
        version=__version__,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on environment in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "authentication_error", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(
        request: Request, exc: AuthorizationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "authorization_error", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "not_found", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(ConflictError)
    async def conflict_error_handler(
        request: Request, exc: ConflictError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "conflict", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(AlreadyApprovedError)
    async def already_approved_error_handler(
        request: Request, exc: AlreadyApprovedError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "already_approved", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(ApprovalLimitExceededError)
    async def approval_limit_error_handler(
        request: Request, exc: ApprovalLimitExceededError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": "approval_limit_exceeded", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(InvalidStateError)
    async def invalid_state_error_handler(
        request: Request, exc: InvalidStateError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_state", "message": exc.message, "details": exc.details},
        )

    @app.exception_handler(MMCoreError)
    async def mmcore_error_handler(
        request: Request, exc: MMCoreError
    ) -> JSONResponse:
        logger.error("unhandled_mmcore_error", error=exc.message, details=exc.details)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": exc.message, "details": exc.details},
        )

    # Include API routers
    app.include_router(api_router, prefix="/api/v1")

    return app


# Create application instance
app = create_app()


def run() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )


if __name__ == "__main__":
    run()
