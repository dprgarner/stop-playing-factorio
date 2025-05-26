from sqlite3 import Connection
from typing import Optional, Self


#
# I should probably bin this class
#
class UserState:
    _con: Connection
    discord_id: int
    time_zone: Optional[str]
    blocked: bool

    def __init__(
        self,
        con: Connection,
        discord_id: int,
        time_zone: Optional[str],
        blocked: bool,
    ):
        self._con = con
        self.discord_id = discord_id
        self.time_zone = time_zone
        self.blocked = blocked

    def __repr__(self):
        return f"""UserState({', '.join(x for x in (
            str(self.discord_id), self.time_zone, self.blocked and 'blocked') if x
        )})"""

    @classmethod
    def fetch(cls, con: Connection, discord_id: int) -> Self:
        for time_zone, blocked in con.execute(
            "SELECT time_zone, blocked FROM UserStates WHERE discord_id=?;",
            (discord_id,),
        ):
            return UserState(con, discord_id, time_zone, bool(blocked))
        return UserState(con, discord_id, None, False)

    def save(self):
        with self._con:
            self._con.execute(
                """
                INSERT INTO UserStates(discord_id, time_zone, blocked)
                    VALUES (?, ?, ?)
                    ON CONFLICT(discord_id) DO UPDATE SET time_zone=?, blocked=?;
                """,
                (
                    self.discord_id,
                    self.time_zone,
                    self.blocked,
                    self.time_zone,
                    self.blocked,
                ),
            )
