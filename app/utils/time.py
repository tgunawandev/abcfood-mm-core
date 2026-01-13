"""Timezone and date/time utilities."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Default timezone for ABCFood (Indonesia/Jakarta)
DEFAULT_TZ = ZoneInfo("Asia/Jakarta")


def utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def local_now() -> datetime:
    """Get current time in default timezone (Asia/Jakarta)."""
    return datetime.now(DEFAULT_TZ)


def to_local(dt: datetime) -> datetime:
    """Convert datetime to default timezone.

    Args:
        dt: Datetime to convert (must be timezone-aware)

    Returns:
        Datetime in Asia/Jakarta timezone
    """
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(DEFAULT_TZ)


def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC.

    Args:
        dt: Datetime to convert

    Returns:
        Datetime in UTC timezone
    """
    if dt.tzinfo is None:
        # Assume local timezone if naive
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    return dt.astimezone(timezone.utc)


def days_between(start: datetime, end: datetime | None = None) -> int:
    """Calculate days between two dates.

    Args:
        start: Start date
        end: End date (defaults to now)

    Returns:
        Number of days between dates
    """
    if end is None:
        end = utc_now()
    return (end.date() - start.date()).days


def format_date(dt: datetime, fmt: str = "%Y-%m-%d") -> str:
    """Format datetime as string.

    Args:
        dt: Datetime to format
        fmt: Format string (default: ISO date)

    Returns:
        Formatted date string
    """
    return to_local(dt).strftime(fmt)


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime as string with time.

    Args:
        dt: Datetime to format
        fmt: Format string

    Returns:
        Formatted datetime string
    """
    return to_local(dt).strftime(fmt)


def start_of_day(dt: datetime | None = None) -> datetime:
    """Get start of day (00:00:00) for given date.

    Args:
        dt: Date to get start of (defaults to today)

    Returns:
        Datetime at start of day in default timezone
    """
    if dt is None:
        dt = local_now()
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime | None = None) -> datetime:
    """Get end of day (23:59:59) for given date.

    Args:
        dt: Date to get end of (defaults to today)

    Returns:
        Datetime at end of day in default timezone
    """
    if dt is None:
        dt = local_now()
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
