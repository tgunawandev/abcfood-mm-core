"""Mattermost slash command endpoint."""

from fastapi import APIRouter, Depends, Form, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.security import verify_slash_command_token
from app.models.schemas import SlashCommandRequest, SlashCommandResponse
from app.services.slash_command_service import SlashCommandService, get_slash_command_service

logger = get_logger(__name__)

router = APIRouter(prefix="/slash", tags=["Slash Commands"])


@router.post(
    "/command",
    response_model=SlashCommandResponse,
    summary="Handle Mattermost slash command",
    description="""
    Receives and processes Mattermost slash commands.

    This endpoint handles the following commands:
    - `/erp` - Odoo 16 ERP operations (invoices, pending, sales)
    - `/hr` - Odoo 13 HRIS operations (leave, approvals)
    - `/frappe` - Frappe 15 operations (CRM, orders)
    - `/metabase` - Metabase dashboard/question links
    - `/access` - Authentik access requests

    Mattermost sends commands as form-urlencoded POST requests.
    """,
)
async def handle_slash_command(
    # Mattermost sends form-urlencoded data
    channel_id: str = Form(...),
    channel_name: str = Form(default=""),
    command: str = Form(...),
    response_url: str = Form(default=""),
    team_domain: str = Form(default=""),
    team_id: str = Form(default=""),
    text: str = Form(default=""),
    token: str = Form(...),
    trigger_id: str = Form(default=""),
    user_id: str = Form(...),
    user_name: str = Form(default=""),
    settings: Settings = Depends(get_settings),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandResponse:
    """Handle incoming Mattermost slash command.

    Security:
        - In production: MM_SLASH_TOKEN must be set and match
        - In development: Token verification is optional (warning logged)
        - Token is generated when creating slash command in Mattermost

    Args:
        channel_id: Channel where command was invoked
        channel_name: Name of the channel
        command: The slash command (e.g., /erp)
        response_url: URL for delayed responses
        team_domain: Team domain
        team_id: Team ID
        text: Text after the command
        token: Verification token
        trigger_id: Trigger ID for interactive dialogs
        user_id: Mattermost user ID
        user_name: Mattermost username
        settings: Application settings
        service: Slash command service

    Returns:
        SlashCommandResponse for Mattermost to display

    Raises:
        HTTPException 401: If token is invalid or missing in production
    """
    # Verify slash command token (REQUIRED in production)
    if settings.mm_slash_token:
        if not verify_slash_command_token(token, settings):
            logger.warning(
                "slash_token_invalid",
                command=command,
                user_id=user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid slash command token",
            )
    elif settings.app_env != "development":
        # In production/staging, token MUST be configured
        logger.error(
            "slash_token_not_configured",
            command=command,
            env=settings.app_env,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Slash command token not configured",
        )
    else:
        # Development mode - allow without token but log warning
        logger.warning(
            "slash_token_skipped_dev_mode",
            command=command,
            user_id=user_id,
        )

    # Build request object
    request = SlashCommandRequest(
        channel_id=channel_id,
        channel_name=channel_name,
        command=command,
        response_url=response_url,
        team_domain=team_domain,
        team_id=team_id,
        text=text,
        token=token,
        trigger_id=trigger_id,
        user_id=user_id,
        user_name=user_name,
    )

    logger.info(
        "slash_command_processing",
        command=command,
        text=text,
        user_id=user_id,
        user_name=user_name,
        channel_id=channel_id,
    )

    # Handle the command
    response = await service.handle_command(request)

    logger.info(
        "slash_command_handled",
        command=command,
        response_type=response.response_type,
    )

    return response


@router.get(
    "/help",
    response_model=SlashCommandResponse,
    summary="Get slash command help",
    description="Returns help text for all available slash commands.",
)
async def get_slash_help() -> SlashCommandResponse:
    """Get help for all slash commands."""
    from app.models.schemas import MattermostAttachment

    return SlashCommandResponse(
        response_type="ephemeral",
        text="**mm-core Slash Commands**",
        attachments=[
            MattermostAttachment(
                color="#3498db",
                title="/erp - Odoo 16 ERP",
                text="`/erp invoice <id>` | `/erp pending` | `/erp sales`",
            ),
            MattermostAttachment(
                color="#9b59b6",
                title="/hr - Odoo 13 HRIS",
                text="`/hr leave status` | `/hr pending`",
            ),
            MattermostAttachment(
                color="#e74c3c",
                title="/frappe - Frappe 15",
                text="`/frappe crm leads` | `/frappe order <id>`",
            ),
            MattermostAttachment(
                color="#509EE3",
                title="/metabase - Analytics",
                text="`/metabase dashboard <name>` | `/metabase question <id>`",
            ),
            MattermostAttachment(
                color="#fd4b2d",
                title="/access - Authentik",
                text="`/access request <app>` | `/access status`",
            ),
        ],
    )
