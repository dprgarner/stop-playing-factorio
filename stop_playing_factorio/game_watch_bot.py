from datetime import datetime, timedelta, UTC
import logging
from typing import List, Optional

import discord
from discord.ext import commands, tasks

from stop_playing_factorio.relative_notifications import RelativeNotification

logger = logging.getLogger()


class GameWatchBot(commands.Bot):
    def __init__(
        self,
        game: str,
        relative_notifications: List[RelativeNotification],
        *args,
        **kwargs,
    ):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(*args, **kwargs, command_prefix="$", intents=intents)
        self.game = game
        self.relative_notifications = relative_notifications
        self.queued_notifications = {}

    def is_playing_since(self, member: discord.Member) -> Optional[datetime]:
        """
        Returns the datetime the member has been playing this game since, or
        None if the user is not playing this game.
        """
        for activity in member.activities:
            if (
                activity.type == discord.ActivityType.playing
                and activity.name == self.game
                and activity.created_at
            ):
                return activity.created_at

    @property
    def actively_playing(self):
        for guild in self.guilds:
            for member in guild.members:
                playing_since = self.is_playing_since(member)
                if playing_since:
                    yield (member, playing_since)

    def set_notifications(self, member_name: str, playing_since: datetime):
        self.queued_notifications[member_name] = []
        for n in self.relative_notifications:
            t = playing_since + timedelta(minutes=n.minutes)
            if t > datetime.now(tz=UTC):
                self.queued_notifications[member_name].append((t, n.message))

    async def send_dm(self, member: discord.Member, message: str):
        logger.info(f"Attempting to message {member.name}")
        channel = member.dm_channel or await member.create_dm()
        await channel.send(message)
        logger.info("Message sent to {member.name}: {message}")

    async def on_ready(self):
        logger.info(
            f"Bot logged in as {self.user}. Finding players actively playing {self.game}..."
        )
        for member, playing_since in self.actively_playing:
            logger.info(
                f"{member.name} is playing {self.game}, setting queued notifications"
            )
            self.set_notifications(member.name, playing_since)
        self.check_watched_games.start()

    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        playing_since = self.is_playing_since(after)
        if not playing_since and after.name in self.queued_notifications:
            logger.info(
                f"{after.name} no longer playing {self.game}, clearing queued notifications"
            )
            del self.queued_notifications[after.name]
        if playing_since and after.name not in self.queued_notifications:
            logger.info(
                f"{after.name} now playing {self.game}, setting queued notifications"
            )
            self.set_notifications(after.name, playing_since)

    @tasks.loop(seconds=60)
    async def check_watched_games(self):
        """
        Check whether anyone needs a nudge.
        """
        logger.info("Checking active players...")
        for member, _ in self.actively_playing:
            if member.name in self.queued_notifications:
                due_notifications = [
                    q
                    for q in self.queued_notifications[member.name]
                    if q[0] <= datetime.now(tz=UTC)
                ]
                logger.info(
                    f"Notifications due for {member.name}: {len(due_notifications)}"
                )
                self.queued_notifications[member.name] = [
                    q
                    for q in self.queued_notifications[member.name]
                    if q[0] > datetime.now(tz=UTC)
                ]
                if len(due_notifications):
                    await self.send_dm(member, due_notifications.pop()[1])
