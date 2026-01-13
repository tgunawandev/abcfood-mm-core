"""API v1 router - aggregates all v1 endpoints."""

from fastapi import APIRouter

from app.api.v1 import approvals, context, digest, health, metrics, pending, slash

# Create main API v1 router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router)
api_router.include_router(approvals.router)
api_router.include_router(metrics.router)
api_router.include_router(digest.router)
api_router.include_router(context.router)
api_router.include_router(pending.router)
api_router.include_router(slash.router)
