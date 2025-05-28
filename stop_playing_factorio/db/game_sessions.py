from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Generator, Optional

import pytz
from sqlite3 import Connection


@dataclass
class GameSession:
    discord_id: int
    started_at: datetime
    duration_nudge_frequency: int
    lateness_nudge_frequency: int
    latest_nudge: datetime
    time_zone_str: Optional[str]

    @property
    def time_zone(self):
        return pytz.timezone(self.time_zone_str or "Europe/London")

    @property
    def next_duration_nudge_due(self) -> datetime:
        """
        Calculates the time when the next "duration" nudge is due, i.e. a
        reminder that a member has been playing the game for more than a certain
        length of time.

        Nudges are due every `duration_nudge_frequency` minutes.
        """
        next_duration_nudge_due = self.started_at
        latest_nudge = self.latest_nudge or self.started_at
        while next_duration_nudge_due <= latest_nudge:
            next_duration_nudge_due += timedelta(minutes=self.duration_nudge_frequency)
        return next_duration_nudge_due

    @property
    def lateness_threshold(self) -> datetime:
        """
        The "lateness threshold" is the time at which "lateness" nudges start -
        this is 11pm local time on the day the game session starts (or the day
        before if the session starts between midnight and 6am).
        """
        local_started_at = self.started_at.astimezone(self.time_zone)
        local_lateness_threshold = local_started_at.replace(
            hour=6, minute=0, second=0, microsecond=0
        )
        if local_lateness_threshold < local_started_at:
            local_lateness_threshold += timedelta(days=1)
        local_lateness_threshold -= timedelta(hours=7)
        lateness_threshold = local_lateness_threshold.astimezone(pytz.utc)
        return lateness_threshold

    @property
    def next_lateness_nudge_due(self) -> datetime:
        """
        Calculates the time when the next "lateness" nudge is due, i.e. a
        reminder that it's getting late. These start at the `lateness_threshold`
        time, and are then due every `lateness_nudge_frequency` minutes
        afterwards.
        """
        next_lateness_nudge_due = self.lateness_threshold
        if self.latest_nudge:
            while next_lateness_nudge_due <= self.latest_nudge:
                next_lateness_nudge_due += timedelta(
                    minutes=self.lateness_nudge_frequency
                )
        return next_lateness_nudge_due

    @property
    def next_nudge_due(self) -> datetime:
        return (
            max(self.next_duration_nudge_due, self.next_lateness_nudge_due)
            if abs(self.next_duration_nudge_due - self.next_lateness_nudge_due)
            < timedelta(minutes=15)
            else min(self.next_duration_nudge_due, self.next_lateness_nudge_due)
        )

    @property
    def duration(self) -> timedelta:
        return datetime.now(pytz.utc) - self.started_at


def get_game_sessions(con: Connection) -> Generator[GameSession, None, None]:
    for row in con.execute(
        """
        SELECT GS.discord_id,
            GS.started_at,
            GS.duration_nudge_frequency,
            GS.lateness_nudge_frequency,
            GS.latest_nudge,
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
        (discord_id,),
    )


def stop_inactive_game_sessions(
    con: Connection, actively_playing_members: list[int, Optional[datetime]]
):
    # sqlite3 doesn't support array inputs - this should be fine as long as the
    # bot's not trying to bother a thousand people at once.
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


def update_latest_nudge(con: Connection, discord_id: int):
    con.execute(
        """
        UPDATE GameSessions
            SET latest_nudge = CURRENT_TIMESTAMP
            WHERE discord_id = ?
        """,
        (discord_id,),
    )
