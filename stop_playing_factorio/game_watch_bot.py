from datetime import datetime, timedelta
import logging
import sqlite3
import pytz
from typing import Optional

import discord
from discord.ext import commands, tasks

from stop_playing_factorio.db import connect
from stop_playing_factorio.db.game_sessions import (
    GameSession,
    delete_stale_game_sessions,
    get_game_sessions,
    is_in_game_session,
    start_game_session,
    start_game_sessions,
    stop_game_session,
    stop_inactive_game_sessions,
    update_latest_nudge,
)
from stop_playing_factorio.db.conversations import (
    delete_stale_conversations,
    get_conversation,
    save_conversation,
)
from stop_playing_factorio.llm import get_instructions, query_llm
from stop_playing_factorio.llm.nudge_prompt import get_nudge_prompt


logger = logging.getLogger()


class GameWatchBot(commands.Bot):
    """
    Tells people to stop playing Factorio.

    TODO: we want an agent to be able to:
    - Change time zones
    - Stop bothering me this session
    - Change notification schedule.
    """

    def __init__(
        self,
        game: str,
        *args,
        **kwargs,
    ):
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True
        super().__init__(*args, **kwargs, command_prefix="$", intents=intents)
        self.game = game

    def playing_activity(self, member: discord.Member) -> Optional[discord.Activity]:
        """
        Returns the relevant playing activity, if the member is playing the
        game.
        """
        for activity in member.activities:
            if (
                activity.type == discord.ActivityType.playing
                and activity.name == self.game
            ):
                return activity

    @property
    def actively_playing_members(self):
        """
        Retrieves the full list of members actively playing the game from all
        the bot's guilds.
        """
        deduplicated_members = set()
        for guild in self.guilds:
            for member in guild.members:
                if member.id in deduplicated_members:
                    continue
                activity = self.playing_activity(member)
                if activity:
                    yield (member.id, activity.created_at)
                    deduplicated_members.add(member.id)

    async def on_ready(self):
        logger.info(
            f"Bot logged in as {self.user}. Finding players actively playing {self.game}..."
        )
        self.sync_data.start()
        self.check_for_nudges.start()

    async def on_presence_update(self, _before: discord.Member, after: discord.Member):
        con = connect()
        activity = self.playing_activity(after)
        if activity:
            logger.info(f"{after.name}({after.id}) is now playing {self.game}")
            start_game_session(con, after.id, activity.created_at)
        else:
            logger.info(f"{after.name}({after.id}) is not playing {self.game}")
            stop_game_session(con, after.id)

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            logger.info("Message seen, but sent by the bot")
            return

        con = connect()
        logger.info(f"Received message: {message.content}")
        async with message.channel.typing():
            conversation = get_conversation(con, message.author.id)
            conversation.add_user_message(message.content)
            msg_response = query_llm(
                get_instructions(
                    message.author,
                    is_playing=is_in_game_session(con, message.author.id),
                ),
                conversation,
            )
            conversation.add_assistant_message(msg_response)
            await message.reply(msg_response)
            logger.info(f"Reply sent to {message.author.name}: {msg_response}")
            save_conversation(con, conversation)

    @tasks.loop(minutes=15)
    async def sync_data(self):
        """
        Syncs the active game sessions pulled from the Discord API with the
        database-persisted game sessions, and reaps stale game sessions and
        conversations.

        The game sessions table is also continuously updated with the
        `on_presence_update` callback, so this task is mostly used to sync on
        start-up, to reap stale game sessions and conversations and to recover
        if events are unprocessed for any reason.
        """
        con = connect()

        try:
            logger.info("Syncing active game sessions...")
            actively_playing_members = list(self.actively_playing_members)
            start_game_sessions(con, actively_playing_members)
            stop_inactive_game_sessions(con, actively_playing_members)
            delete_stale_game_sessions(con)

            logger.info("Clearing stale conversations...")
            delete_stale_conversations(con)
        except Exception:
            logger.error(
                f"Could not sync game sessions and conversations",
                exc_info=True,
            )

    async def send_nudge(self, con: sqlite3.Connection, game_session: GameSession):
        user = self.get_user(game_session.discord_id) or await self.fetch_user(
            game_session.discord_id
        )

        dm_channel = user.dm_channel or await user.create_dm()
        async with dm_channel.typing():
            conversation = get_conversation(con, game_session.discord_id)
            nudge_prompt = get_nudge_prompt(game_session)
            logger.info(f"Created nudge prompt: {nudge_prompt}")
            conversation.add_user_message(nudge_prompt)
            nudge = query_llm(get_instructions(user, is_playing=True), conversation)
            logger.info(f"Nudge generated from LLM: {nudge}")
            conversation.add_assistant_message(nudge)
            await dm_channel.send(nudge)
            logger.info(f"Nudge DM'ed to user: {user.id}")

        save_conversation(con, conversation)
        update_latest_nudge(con, game_session.discord_id)

    @tasks.loop(minutes=1)
    async def check_for_nudges(self):
        """
        Check if anyone needs a nudge.
        Assumes that the GameSessions are up-to-date.
        """
        logger.info("Checking for nudges...")
        con = connect()
        for game_session in get_game_sessions(con):
            if game_session.next_nudge_due < datetime.now(tz=pytz.utc):
                try:
                    logger.info(f"Nudge due for {game_session.discord_id}")
                    await self.send_nudge(con, game_session)
                except Exception:
                    logger.error(
                        f"Could not send nudge to user {game_session.discord_id}",
                        exc_info=True,
                    )
