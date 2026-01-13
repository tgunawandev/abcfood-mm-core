"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="abcfood-mm-core", description="Application name")
    app_env: Literal["development", "staging", "production"] = Field(
        default="development", description="Environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    api_key: str = Field(description="API key for authentication")

    # PostgreSQL (Odoo DBs + Audit Logs)
    pg_host: str = Field(default="88.99.226.47", description="PostgreSQL host")
    pg_port: int = Field(default=5432, description="PostgreSQL port")
    pg_user: str = Field(default="postgres", description="PostgreSQL user")
    pg_password: str = Field(description="PostgreSQL password")
    pg_audit_db: str = Field(default="mm_audit", description="Audit logs database")

    # Odoo XML-RPC - Multi-server architecture
    # Production: each database has its own server
    # Development: all databases on dev servers
    #
    # Odoo 16 (Main ERP - tln_db, ieg_db, tmi_db):
    #   Dev: odoo-16-dev.abcfood.app
    #   Prod: tln.abcfood.app, ieg.abcfood.app, tmi.abcfood.app
    #
    # Odoo 13 (HRIS - hris_db):
    #   Dev: odoo-13-dev.abcfood.app
    #   Prod: TBD
    odoo_host_tln: str = Field(
        default="odoo-16-dev.abcfood.app",
        description="Odoo 16 host for tln_db",
    )
    odoo_host_ieg: str = Field(
        default="odoo-16-dev.abcfood.app",
        description="Odoo 16 host for ieg_db",
    )
    odoo_host_tmi: str = Field(
        default="odoo-16-dev.abcfood.app",
        description="Odoo 16 host for tmi_db",
    )
    odoo_host_hris: str = Field(
        default="odoo-13-dev.abcfood.app",
        description="Odoo 13 host for hris_db",
    )
    odoo_port: int = Field(default=8069, description="Odoo port")
    odoo_user: str = Field(default="service_account", description="Odoo user")
    odoo_password: str = Field(description="Odoo password")

    # ClickHouse (Analytics only)
    ch_host: str = Field(default="138.199.213.219", description="ClickHouse host")
    ch_port: int = Field(default=8123, description="ClickHouse HTTP port")
    ch_user: str = Field(default="clickhouse", description="ClickHouse user")
    ch_password: str = Field(description="ClickHouse password")

    # Optional: Mattermost webhook signature verification
    mm_webhook_secret: str | None = Field(default=None, description="Mattermost webhook secret")

    # Authentik OAuth2/JWT
    authentik_issuer: str = Field(
        default="https://auth.abcfood.app",
        description="Authentik issuer URL",
    )
    authentik_jwks_uri: str | None = Field(
        default=None,
        description="Authentik JWKS endpoint (defaults to {issuer}/application/o/mm-core/jwks/)",
    )
    authentik_client_id: str | None = Field(
        default=None,
        description="OAuth2 client ID for mm-core",
    )
    authentik_client_secret: str | None = Field(
        default=None,
        description="OAuth2 client secret",
    )

    # Mattermost Slash Commands
    mm_slash_token: str | None = Field(
        default=None,
        description="Mattermost slash command verification token",
    )
    mm_api_url: str = Field(
        default="https://mm.abcfood.app/api/v4",
        description="Mattermost API base URL",
    )
    mm_bot_token: str | None = Field(
        default=None,
        description="Mattermost bot token for user lookups",
    )

    # Frappe
    frappe_site: str = Field(
        default="erp.abcfood.app",
        description="Frappe site domain",
    )
    frappe_api_key: str | None = Field(
        default=None,
        description="Frappe API key",
    )
    frappe_api_secret: str | None = Field(
        default=None,
        description="Frappe API secret",
    )

    # Metabase
    mb_domain: str = Field(
        default="mb.abcfood.app",
        description="Metabase domain",
    )
    mb_embedding_secret: str | None = Field(
        default=None,
        description="Metabase embedding secret key for signed URLs",
    )
    mb_session_token: str | None = Field(
        default=None,
        description="Metabase API session token",
    )

    @property
    def authentik_jwks_url(self) -> str:
        """Get JWKS URL (computed or explicit)."""
        if self.authentik_jwks_uri:
            return self.authentik_jwks_uri
        return f"{self.authentik_issuer}/application/o/mm-core/jwks/"

    # Allowed Odoo databases (comma-separated string)
    # Includes both Odoo 16 (tln, ieg, tmi) and Odoo 13 (hris)
    allowed_odoo_dbs_str: str = Field(
        default="tln_db,ieg_db,tmi_db,hris_db",
        alias="allowed_odoo_dbs",
        description="Allowed Odoo databases (comma-separated)",
    )

    @computed_field
    @property
    def allowed_odoo_dbs(self) -> list[str]:
        """Parse comma-separated string to list of allowed databases."""
        return [db.strip() for db in self.allowed_odoo_dbs_str.split(",") if db.strip()]

    @property
    def pg_connection_string(self) -> str:
        """PostgreSQL connection string for audit database."""
        return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_audit_db}"

    def get_odoo_db_connection_string(self, db_name: str) -> str:
        """PostgreSQL connection string for specific Odoo database."""
        if db_name not in self.allowed_odoo_dbs:
            raise ValueError(f"Database {db_name} not in allowed list: {self.allowed_odoo_dbs}")
        return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{db_name}"

    def get_odoo_host(self, db_name: str) -> str:
        """Get Odoo host for specific database.

        Odoo 16 (Main ERP):
        - tln.abcfood.app -> tln_db (prod)
        - ieg.abcfood.app -> ieg_db (prod)
        - tmi.abcfood.app -> tmi_db (prod)
        - odoo-16-dev.abcfood.app (dev)

        Odoo 13 (HRIS):
        - odoo-13-dev.abcfood.app -> hris_db (dev)
        - TBD -> hris_db (prod)
        """
        if db_name not in self.allowed_odoo_dbs:
            raise ValueError(f"Database {db_name} not in allowed list: {self.allowed_odoo_dbs}")

        host_map = {
            "tln_db": self.odoo_host_tln,
            "ieg_db": self.odoo_host_ieg,
            "tmi_db": self.odoo_host_tmi,
            "hris_db": self.odoo_host_hris,
        }
        return host_map.get(db_name, self.odoo_host_tln)

    def get_odoo_version(self, db_name: str) -> int:
        """Get Odoo version for specific database.

        Returns:
            13 for hris_db, 16 for others
        """
        return 13 if db_name == "hris_db" else 16


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
