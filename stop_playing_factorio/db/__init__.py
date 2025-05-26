from datetime import UTC, datetime
import sqlite3


def adapt_datetime_iso(val: datetime) -> str:
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()


def convert_datetime(val: bytes) -> datetime:
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.fromisoformat(val.decode()).replace(tzinfo=UTC)


sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("DATETIME", convert_datetime)


def connect() -> sqlite3.Connection:
    return sqlite3.connect(
        "spfbot.db", detect_types=sqlite3.PARSE_DECLTYPES, isolation_level=None
    )


def create_tables(con: sqlite3.Connection):
    # Only stored when needed. The Discord.py model is usually the
    # source-of-truth for user information.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS UserStates(
            discord_id INTEGER UNIQUE NOT NULL,
            time_zone STRING,
            blocked BOOLEAN DEFAULT FALSE
        );
        """
    )
    # Objects are created when a user starts playing Factorio, and deleted after
    # they've stopped for 15 minutes.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS GameSessions(
            discord_id INTEGER UNIQUE NOT NULL,
            started_at DATETIME NOT NULL,
            ended_at DATETIME,
            muted BOOLEAN DEFAULT FALSE,
            duration_nudge_frequency INTEGER DEFAULT 60,
            lateness_nudge_frequency INTEGER DEFAULT 30,
            latest_nudge DATETIME
        );
        """
    )
    # This is separate from a game session, as an exchange of messages could be
    # in public or private, and when the user is or isn't playing Factorio.
    # Exchanges are deleted after three hours with no more messages.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS UserExchanges(
            discord_id INTEGER UNIQUE NOT NULL,
            latest_message DATETIME DEFAULT CURRENT_TIMESTAMP,
            llm_message_history JSON
        );
        """
    )
