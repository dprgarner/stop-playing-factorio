from datetime import time, UTC
import os
import logging
from logging.handlers import TimedRotatingFileHandler

import discord
from dotenv import load_dotenv

from stop_playing_factorio.db import connect, create_tables
from stop_playing_factorio.game_watch_bot import GameWatchBot


def main() -> None:
    load_dotenv()
    create_tables(connect())

    # bot = GameWatchBot(game="Factorio")
    bot = GameWatchBot(game="Minecraft")

    handler = TimedRotatingFileHandler(
        filename="logs/spfbot.log",
        when="midnight",
        encoding="utf-8",
        utc=True,
        atTime=time(6, 00, tzinfo=UTC),
    )
    discord.utils.setup_logging(level=logging.INFO, handler=handler)
    bot.run(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    main()
