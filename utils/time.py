from datetime import datetime, timezone


def utcnow_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def ms_since(start: datetime) -> int:
    """Return milliseconds elapsed since a given datetime."""
    delta = datetime.now(timezone.utc) - start
    return int(delta.total_seconds() * 1000)