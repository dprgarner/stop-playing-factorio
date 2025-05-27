import json
from sqlite3 import Connection


from dataclasses import dataclass


@dataclass
class Conversation:
    discord_id: int
    llm_message_history: list[object]

    def add_assistant_message(self, content: str):
        self.llm_message_history.append({"role": "assistant", "content": content})

    def add_user_message(self, content: str):
        self.llm_message_history.append({"role": "user", "content": content})


def get_conversation(con: Connection, discord_id: int) -> Conversation:
    for (llm_message_history,) in con.execute(
        """
        SELECT json(llm_message_history)
            FROM Conversations
            WHERE discord_id = ?
            AND latest_message > datetime('now', '-2 hours');
        """,
        (discord_id,),
    ):
        return Conversation(discord_id, json.loads(llm_message_history))
    return Conversation(discord_id, [])


def save_conversation(con: Connection, conversation: Conversation):
    llm_message_history_str = json.dumps(conversation.llm_message_history)
    con.executemany(
        """
        INSERT INTO Conversations(discord_id, llm_message_history) VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE
                SET llm_message_history = ?, latest_message = CURRENT_TIMESTAMP;
        """,
        [(conversation.discord_id, llm_message_history_str, llm_message_history_str)],
    )


def delete_stale_conversations(con: Connection):
    con.execute(
        """
        DELETE FROM Conversations
            WHERE (latest_message < datetime('now', '-2 hours'));
        """
    )
