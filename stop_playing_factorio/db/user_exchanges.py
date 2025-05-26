import json
from sqlite3 import Connection
from typing import Optional


def get_user_exchange(con: Connection, discord_id: int) -> Optional[list]:
    for (llm_message_history,) in con.execute(
        """
            SELECT json(llm_message_history)
            FROM UserExchanges
            WHERE discord_id = ?
            AND latest_message > datetime('now', '-2 hours');
        """,
        (discord_id,),
    ):
        return json.loads(llm_message_history)
    return []


def update_user_exchange(con: Connection, discord_id: int, llm_message_history: list):
    llm_message_history_str = json.dumps(llm_message_history)
    con.executemany(
        """
        INSERT INTO UserExchanges(discord_id, llm_message_history) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE
                SET llm_message_history = ?, latest_message = CURRENT_TIMESTAMP;
        """,
        [(discord_id, llm_message_history_str, llm_message_history_str)],
    )


def delete_stale_user_exchanges(con: Connection):
    con.execute(
        """
        DELETE FROM UserExchanges
            WHERE (latest_message < datetime('now', '-2 hours'));
        """
    )
