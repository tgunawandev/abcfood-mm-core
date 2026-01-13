"""Authentik OAuth2/JWT authentication utilities."""

import time
from typing import Any

import httpx
import jwt
from cachetools import TTLCache
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.exceptions import JWTValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Cache JWKS for 1 hour (3600 seconds)
_jwks_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=10, ttl=3600)


class UserContext(BaseModel):
    """Authenticated user context extracted from JWT."""

    user_id: str = Field(description="Authentik user ID (sub claim)")
    email: str = Field(description="User email address")
    username: str = Field(description="Preferred username")
    name: str = Field(default="", description="Full name")
    groups: list[str] = Field(default_factory=list, description="Authentik groups")
    business_unit: str = Field(default="", description="Primary business unit (from ak-bu-* group)")
    roles: list[str] = Field(default_factory=list, description="Role groups (from ak-role-* groups)")

    @classmethod
    def from_jwt_claims(cls, claims: dict[str, Any]) -> "UserContext":
        """Create UserContext from JWT claims.

        Args:
            claims: Decoded JWT payload

        Returns:
            UserContext instance
        """
        groups = claims.get("groups", [])
        if isinstance(groups, str):
            groups = [groups]

        # Extract business unit from ak-bu-* groups
        business_unit = ""
        for group in groups:
            if group.startswith("ak-bu-"):
                business_unit = group.replace("ak-bu-", "")
                break

        # Extract roles from ak-role-* groups
        roles = [g.replace("ak-role-", "") for g in groups if g.startswith("ak-role-")]

        return cls(
            user_id=claims.get("sub", ""),
            email=claims.get("email", ""),
            username=claims.get("preferred_username", claims.get("email", "")),
            name=claims.get("name", ""),
            groups=groups,
            business_unit=business_unit,
            roles=roles,
        )


class AuthContext(BaseModel):
    """Authentication context - either API key or user JWT."""

    auth_type: str = Field(description="Authentication type: 'api_key' or 'jwt'")
    api_key: str | None = Field(default=None, description="API key if auth_type is api_key")
    user: UserContext | None = Field(default=None, description="User context if auth_type is jwt")

    @property
    def actor(self) -> str:
        """Get actor identifier for audit logging."""
        if self.user:
            return self.user.email
        return "api_key"

    @property
    def actor_role(self) -> str:
        """Get actor role for audit logging."""
        if self.user and self.user.roles:
            return self.user.roles[0]
        return "service"


async def fetch_jwks(jwks_url: str) -> dict[str, Any]:
    """Fetch JWKS from Authentik.

    Args:
        jwks_url: URL to JWKS endpoint

    Returns:
        JWKS dictionary with keys

    Raises:
        JWTValidationError: If JWKS fetch fails
    """
    # Check cache first
    if jwks_url in _jwks_cache:
        logger.debug("jwks_cache_hit", url=jwks_url)
        return _jwks_cache[jwks_url]

    logger.debug("jwks_fetching", url=jwks_url)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks = response.json()
            _jwks_cache[jwks_url] = jwks
            logger.info("jwks_fetched", url=jwks_url, key_count=len(jwks.get("keys", [])))
            return jwks
    except httpx.HTTPError as e:
        logger.error("jwks_fetch_failed", url=jwks_url, error=str(e))
        raise JWTValidationError(f"Failed to fetch JWKS: {e}") from e


def get_signing_key(jwks: dict[str, Any], kid: str | None) -> dict[str, Any]:
    """Get signing key from JWKS by key ID.

    Args:
        jwks: JWKS dictionary
        kid: Key ID from JWT header

    Returns:
        Key dictionary

    Raises:
        JWTValidationError: If key not found
    """
    keys = jwks.get("keys", [])

    # If kid provided, find matching key
    if kid:
        for key in keys:
            if key.get("kid") == kid:
                return key

    # If no kid or not found, try first RSA key
    for key in keys:
        if key.get("kty") == "RSA":
            return key

    raise JWTValidationError("No suitable signing key found in JWKS")


async def validate_jwt(token: str, settings: Settings | None = None) -> UserContext:
    """Validate JWT token from Authentik.

    Args:
        token: JWT token string (without 'Bearer ' prefix)
        settings: Optional settings instance

    Returns:
        UserContext with decoded claims

    Raises:
        JWTValidationError: If token is invalid
    """
    if settings is None:
        settings = get_settings()

    try:
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Fetch JWKS
        jwks = await fetch_jwks(settings.authentik_jwks_url)
        key_data = get_signing_key(jwks, kid)

        # Build public key from JWKS
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

        # Decode and validate token
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=settings.authentik_issuer,
            audience=settings.authentik_client_id,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": settings.authentik_client_id is not None,
            },
        )

        user = UserContext.from_jwt_claims(claims)
        logger.info(
            "jwt_validated",
            user_id=user.user_id,
            email=user.email,
            business_unit=user.business_unit,
        )
        return user

    except jwt.ExpiredSignatureError as e:
        logger.warning("jwt_expired", error=str(e))
        raise JWTValidationError("Token has expired") from e
    except jwt.InvalidTokenError as e:
        logger.warning("jwt_invalid", error=str(e))
        raise JWTValidationError(f"Invalid token: {e}") from e
    except Exception as e:
        logger.error("jwt_validation_failed", error=str(e))
        raise JWTValidationError(f"Token validation failed: {e}") from e


def verify_slash_command_token(token: str, settings: Settings | None = None) -> bool:
    """Verify Mattermost slash command token.

    Args:
        token: Token from slash command payload
        settings: Optional settings instance

    Returns:
        True if token is valid
    """
    if settings is None:
        settings = get_settings()

    if not settings.mm_slash_token:
        logger.warning("slash_token_not_configured")
        return True  # Allow if not configured (dev mode)

    import hmac

    return hmac.compare_digest(token, settings.mm_slash_token)


def create_test_token(
    user_id: str = "test-user",
    email: str = "test@abcfood.app",
    groups: list[str] | None = None,
    expires_in: int = 3600,
) -> str:
    """Create a test JWT token (for development only).

    Args:
        user_id: User ID
        email: User email
        groups: User groups
        expires_in: Token expiry in seconds

    Returns:
        JWT token string
    """
    settings = get_settings()

    if groups is None:
        groups = ["ak-bu-tln", "ak-role-analyst"]

    claims = {
        "sub": user_id,
        "email": email,
        "preferred_username": email.split("@")[0],
        "name": "Test User",
        "groups": groups,
        "iss": settings.authentik_issuer,
        "aud": settings.authentik_client_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }

    # This would need a private key - for real testing use Authentik directly
    # This is just a placeholder for the structure
    return "test-token-placeholder"
