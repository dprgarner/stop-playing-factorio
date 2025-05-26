from datetime import datetime, timedelta
import logging
import pytz
from typing import Optional

import discord
from discord.ext import commands, tasks

from stop_playing_factorio.db import connect
from stop_playing_factorio.db.game_sessions import (
    delete_stale_game_sessions,
    get_game_sessions,
    start_game_session,
    start_game_sessions,
    stop_game_session,
    stop_inactive_game_sessions,
    update_latest_nudge,
)
from stop_playing_factorio.db.user_exchanges import (
    delete_stale_user_exchanges,
    get_user_exchange,
    update_user_exchange,
)

logger = logging.getLogger()


class GameWatchBot(commands.Bot):
    """
    Tells people to stop playing Factorio.

    TODO: we want an agent to be able to:
    - Change time zones
    - Stop bothering me this session
    - Change notification schedule (this will be hard, though - need a good model of notifications, and confidence that GPT can generate them. )
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

    async def send_dm(self, member: discord.Member, txt: str) -> discord.Message:
        """
        Sends a DM.
        """
        logger.info(f"Attempting to message {member.name}")
        channel = member.dm_channel or await member.create_dm()
        message = await channel.send(txt)
        logger.info(f"Message sent to {member.name}: {txt}")
        return message

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
            logger.info(f"{after.name}({after.id}) has stopped playing {self.game}")
            stop_game_session(con, after.id)

    @tasks.loop(minutes=15)
    async def sync_data(self):
        """
        Syncs the active game sessions pulled from the Discord API with the
        database-persisted game sessions, and reaps stale game sessions and
        user-exchanges.

        This table is also continuously updated with the `on_presence_update`
        callback, so is mostly used to sync on start-up and to reap stale game
        sessions.
        """
        con = connect()

        # TODO delete
        start_game_session(
            con,
            241263400506621952,
            datetime.now(tz=pytz.utc) - timedelta(minutes=75),
        )
        return
        # TODO delete

        logger.info("Syncing active game sessions...")
        actively_playing_members = list(self.actively_playing_members)
        start_game_sessions(con, actively_playing_members)
        stop_inactive_game_sessions(con, actively_playing_members)
        delete_stale_game_sessions(con)

        logger.info("Clearing stale user exchanges...")
        delete_stale_user_exchanges(con)

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
                logger.info(f"Nudge due for {game_session.discord_id}")
                user_exchange = get_user_exchange(con, game_session.discord_id)

                # Construct a relevant prompt - contains time played, local time, message history
                # Send the prompt with the exchange to OpenAI
                # (There won't be any agentic actions at this time, so not important here)
                # Send a DM with the prompt response.

                update_user_exchange(
                    con, game_session.discord_id, user_exchange + [{"baz": "qux"}]
                )
                update_latest_nudge(con, game_session.discord_id)
