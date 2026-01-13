"""Security utilities for API authentication."""

import hashlib
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.auth import AuthContext, UserContext, validate_jwt, verify_slash_command_token
from app.core.config import Settings, get_settings
from app.core.exceptions import JWTValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)


async def verify_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> str:
    """Verify API key from request header.

    Args:
        x_api_key: API key from X-API-Key header
        settings: Application settings

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not x_api_key:
        logger.warning("api_key_missing", message="API key not provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not hmac.compare_digest(x_api_key, settings.api_key):
        logger.warning("api_key_invalid", message="Invalid API key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key


async def verify_auth(
    x_api_key: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    """Verify authentication - supports API key OR JWT Bearer token.

    This enables dual authentication:
    - API key (X-API-Key header) for service-to-service calls (n8n)
    - JWT Bearer token (Authorization header) for user calls (Mattermost)

    Args:
        x_api_key: API key from X-API-Key header
        authorization: Bearer token from Authorization header
        settings: Application settings

    Returns:
        AuthContext with authentication details

    Raises:
        HTTPException: If neither auth method succeeds
    """
    # Try API key first (service-to-service)
    if x_api_key:
        if hmac.compare_digest(x_api_key, settings.api_key):
            logger.debug("auth_api_key_valid")
            return AuthContext(auth_type="api_key", api_key=x_api_key)
        logger.warning("auth_api_key_invalid")

    # Try JWT Bearer token (user authentication)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        try:
            user = await validate_jwt(token, settings)
            logger.debug("auth_jwt_valid", user_id=user.user_id)
            return AuthContext(auth_type="jwt", user=user)
        except JWTValidationError as e:
            logger.warning("auth_jwt_invalid", error=str(e))

    # Neither auth method succeeded
    logger.warning("auth_failed", has_api_key=bool(x_api_key), has_bearer=bool(authorization))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": 'Bearer realm="mm-core", ApiKey'},
    )


async def verify_jwt_only(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> UserContext:
    """Verify JWT Bearer token only (no API key fallback).

    Use this for endpoints that require user context.

    Args:
        authorization: Bearer token from Authorization header
        settings: Application settings

    Returns:
        UserContext with user details

    Raises:
        HTTPException: If JWT is missing or invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": 'Bearer realm="mm-core"'},
        )

    token = authorization[7:]
    try:
        return await validate_jwt(token, settings)
    except JWTValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": 'Bearer realm="mm-core"'},
        ) from e


async def verify_slash_token(
    token: str,
    settings: Settings = Depends(get_settings),
) -> bool:
    """Verify Mattermost slash command token.

    Args:
        token: Token from slash command payload
        settings: Application settings

    Returns:
        True if valid

    Raises:
        HTTPException: If token is invalid
    """
    if not verify_slash_command_token(token, settings):
        logger.warning("slash_token_invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid slash command token",
        )
    return True


def verify_mattermost_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify Mattermost webhook signature.

    Mattermost sends a HMAC-SHA256 signature in the X-Mattermost-Signature header.

    Args:
        payload: Raw request body
        signature: Signature from X-Mattermost-Signature header
        secret: Webhook secret configured in Mattermost

    Returns:
        True if signature is valid
    """
    expected = hmac.new(
        key=secret.encode(),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


# Type aliases for dependency injection
ApiKeyDep = Annotated[str, Depends(verify_api_key)]
AuthDep = Annotated[AuthContext, Depends(verify_auth)]
UserDep = Annotated[UserContext, Depends(verify_jwt_only)]
