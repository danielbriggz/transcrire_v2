import sqlite3
from pathlib import Path
from typing import Generator
from contextlib import contextmanager

from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Apply pragmas to every new connection."""
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row  # rows accessible by column name


def get_connection() -> sqlite3.Connection:
    """
    Returns a configured SQLite connection.

    Use this for long-lived connections (e.g. repositories).
    Caller is responsible for closing.
    """
    db_path = config.db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _configure_connection(conn)
    logger.debug({"event": "db_connection_opened", "path": str(db_path)})
    return conn


@contextmanager
def get_cursor(conn: sqlite3.Connection) -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for transactional cursor usage.

    Usage:
        with get_cursor(conn) as cursor:
            cursor.execute("INSERT INTO ...")

    Commits on success, rolls back on exception.
    """
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error({"event": "db_transaction_failed", "error": str(e)})
        raise


def run_migrations(conn: sqlite3.Connection) -> None:
    """
    Execute schema.sql against the database.
    Safe to run on every startup — all statements use CREATE TABLE IF NOT EXISTS.
    """
    schema_path = Path(__file__).parent / "schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_cursor(conn) as cursor:
        cursor.executescript(schema_sql)

    logger.info({"event": "migrations_complete", "schema": str(schema_path)})