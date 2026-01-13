"""Dependency injection for API routes."""

from typing import Annotated

from fastapi import Depends, Query

from app.core.config import Settings, get_settings
from app.core.security import verify_api_key
from app.models.enums import OdooDatabase


async def get_db_param(
    db: OdooDatabase = Query(description="Odoo database to use"),
    settings: Settings = Depends(get_settings),
) -> str:
    """Validate and return database parameter.

    Args:
        db: Database name from query parameter
        settings: Application settings

    Returns:
        Validated database name
    """
    return db.value


# Type aliases for dependency injection
SettingsDep = Annotated[Settings, Depends(get_settings)]
ApiKeyDep = Annotated[str, Depends(verify_api_key)]
DbDep = Annotated[str, Depends(get_db_param)]
