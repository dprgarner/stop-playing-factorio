from datetime import datetime, timedelta
import logging
import pytz
from sqlite3 import Connection
from typing import Optional

import discord
from discord.ext import commands, tasks

from stop_playing_factorio.db.game_sessions import (
    GameSession,
    delete_stale_game_sessions,
    get_game_sessions,
    start_game_session,
    start_game_sessions,
    stop_game_session,
    stop_inactive_game_sessions,
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
        con: Connection,
        *args,
        **kwargs,
    ):
        intents = discord.Intents.default()
        intents.members = True
        intents.presences = True
        super().__init__(*args, **kwargs, command_prefix="$", intents=intents)
        self.game = game
        self.con = con

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
        self.sync_game_sessions.start()
        self.check_for_nudges.start()

    async def on_presence_update(self, _before: discord.Member, after: discord.Member):
        activity = self.playing_activity(after)
        with self.con:
            if activity:
                logger.info(f"{after.name}({after.id}) is now playing {self.game}")
                start_game_session(self.con, after.id, activity.created_at)
            else:
                logger.info(f"{after.name}({after.id}) has stopped playing {self.game}")
                stop_game_session(self.con, after.id)

    @tasks.loop(minutes=15)
    async def sync_game_sessions(self):
        """
        Syncs the active game sessions pulled from the Discord API with the
        database-persisted game sessions.

        This table is also continuously updated with the `on_presence_update`
        callback, so is mostly used to sync on start-up and to reap stale game sessions.
        """
        logger.info("Syncing active game sessions...")
        actively_playing_members = list(self.actively_playing_members)
        with self.con:
            start_game_sessions(self.con, actively_playing_members)
            stop_inactive_game_sessions(self.con, actively_playing_members)
            delete_stale_game_sessions(self.con)

    def get_next_duration_nudge(self, game_session: GameSession):
        """
        Calculates the time when the next "duration" nudge is due, i.e. a
        reminder that a member has been playing the game for more than a certain
        length of time.

        Nudges are due every `duration_nudge_frequency` minutes.
        """
        next_duration_nudge_due = game_session.started_at
        latest_duration_nudge = (
            game_session.latest_duration_nudge or game_session.started_at
        )
        while next_duration_nudge_due <= latest_duration_nudge:
            next_duration_nudge_due += timedelta(
                minutes=game_session.duration_nudge_frequency
            )
        return next_duration_nudge_due

    def get_next_lateness_nudge(self, game_session: GameSession):
        """
        Calculates the time when the next "lateness" nudge is due, i.e. a
        reminder that it's getting late.

        Nudges start at 11pm local time on the day the game session starts (or
        the day before if the session starts between midnight and 6am), and are
        due every `lateness_nudge_frequency` minutes afterwards.
        """
        local_started_at = game_session.started_at.astimezone(game_session.time_zone)
        local_lateness_threshold = local_started_at.replace(
            hour=6, minute=0, second=0, microsecond=0
        )
        if local_lateness_threshold < local_started_at:
            local_lateness_threshold += timedelta(days=1)
        local_lateness_threshold -= timedelta(hours=7)
        lateness_threshold = local_lateness_threshold.astimezone(pytz.utc)
        next_lateness_nudge_due = lateness_threshold
        if game_session.latest_lateness_nudge:
            while next_lateness_nudge_due <= game_session.latest_lateness_nudge:
                next_lateness_nudge_due += timedelta(
                    minutes=game_session.lateness_nudge_frequency
                )
        return next_lateness_nudge_due

    @tasks.loop(minutes=1)
    async def check_for_nudges(self):
        """
        Check if anyone needs a nudge.
        Assumes that the GameSessions are up-to-date.
        """
        logger.info("Checking for nudges...")
        for game_session in get_game_sessions(self.con):
            next_duration_nudge_due = self.get_next_duration_nudge(game_session)
            print("next duration nudge due:", next_duration_nudge_due)

            next_lateness_nudge_due = self.get_next_lateness_nudge(game_session)
            print(f"Next lateness nudge due: {next_lateness_nudge_due}")
