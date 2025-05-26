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
from stop_playing_factorio.llm.generate_nudge import generate_nudge

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

    async def send_dm(self, user: discord.User, txt: str) -> discord.Message:
        """
        Sends a DM.
        """
        logger.info(f"Attempting to message {user.name}")
        channel = user.dm_channel or await user.create_dm()
        message = await channel.send(txt)
        logger.info(f"Message sent to {user.name}: {txt}")
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

        try:
            logger.info("Syncing active game sessions...")
            actively_playing_members = list(self.actively_playing_members)
            start_game_sessions(con, actively_playing_members)
            stop_inactive_game_sessions(con, actively_playing_members)
            delete_stale_game_sessions(con)

            logger.info("Clearing stale user exchanges...")
            delete_stale_user_exchanges(con)
        except Exception:
            logger.error(
                f"Could not sync game sessions and user exchanges",
                exc_info=True,
            )

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
                    user_exchange = get_user_exchange(con, game_session.discord_id)

                    user = self.get_user(
                        game_session.discord_id
                    ) or await self.fetch_user(game_session.discord_id)

                    async with user.dm_channel.typing():
                        nudge = generate_nudge(user, game_session, user_exchange)
                        await self.send_dm(user, nudge)

                    update_user_exchange(
                        con,
                        game_session.discord_id,
                        user_exchange + [{"role": "assistant", "content": nudge}],
                    )
                    update_latest_nudge(con, game_session.discord_id)
                except Exception:
                    logger.error(
                        f"Could not send nudge to user {game_session.discord_id}",
                        exc_info=True,
                    )
