from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generator, Optional

import pytz
from sqlite3 import Connection


@dataclass
class GameSession:
    discord_id: int
    started_at: datetime
    duration_nudge_frequency: int
    latest_duration_nudge: datetime
    lateness_nudge_frequency: int
    latest_lateness_nudge: datetime
    time_zone_str: str

    @property
    def time_zone(self):
        return pytz.timezone(self.time_zone_str or "Europe/London")


def get_game_sessions(
    con: Connection,
) -> Generator[GameSession, None, None]:
    for row in con.execute(
        """
            SELECT GS.discord_id,
                GS.started_at,
                GS.duration_nudge_frequency,
                GS.latest_duration_nudge,
                GS.lateness_nudge_frequency,
                GS.latest_lateness_nudge,
                US.time_zone
            FROM GameSessions GS
                LEFT JOIN UserStates US ON GS.discord_id = US.discord_id
                WHERE GS.ended_at IS NULL
                AND GS.muted = FALSE
                AND US.blocked IS NOT TRUE;
            """
    ):
        yield GameSession(*row)


def start_game_session(
    con: Connection, discord_id: int, started_at: Optional[datetime]
):
    con.executemany(
        """
        INSERT INTO GameSessions(discord_id, started_at) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET ended_at = NULL;
        """,
        [(discord_id, started_at or datetime.now(tz=UTC))],
    )


def start_game_sessions(
    con: Connection, actively_playing_members: list[int, Optional[datetime]]
):
    con.executemany(
        """
        INSERT INTO GameSessions(discord_id, started_at) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET ended_at = NULL;
        """,
        [
            (discord_id, started_at or datetime.now(tz=UTC))
            for discord_id, started_at in actively_playing_members
        ],
    )


def stop_game_session(con: Connection, discord_id: int):
    con.execute(
        """
        UPDATE GameSessions
            SET ended_at = CURRENT_TIMESTAMP
            WHERE ended_at IS NULL
            AND discord_id = ?
        """,
        (discord_id),
    )


def stop_inactive_game_sessions(
    con: Connection, actively_playing_members: list[int, Optional[datetime]]
):
    con.execute(
        f"""
        UPDATE GameSessions
            SET ended_at = CURRENT_TIMESTAMP
            WHERE ended_at IS NULL
            AND discord_id NOT IN ({','.join('?' * len(actively_playing_members))});
        """,
        [discord_id for discord_id, _ in actively_playing_members],
    )


def delete_stale_game_sessions(con: Connection):
    con.execute(
        """
        DELETE FROM GameSessions
            WHERE (ended_at IS NOT NULL AND ended_at < datetime('now', '-5 minutes'));
        """
    )
    # OR EXISTS ( SELECT discord_id FROM UserStates WHERE UserStates.discord_id = GameSessions.discord_id AND UserStates.blocked = TRUE );
