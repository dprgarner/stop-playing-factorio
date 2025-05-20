import os
import logging

import discord
from dotenv import load_dotenv

from stop_playing_factorio.game_watch_bot import GameWatchBot
from stop_playing_factorio.relative_notifications import FACTORIO_RELATIVE_NOTIFICATIONS


load_dotenv()

bot = GameWatchBot(
    game="Factorio", relative_notifications=FACTORIO_RELATIVE_NOTIFICATIONS
)

if __name__ == "__main__":
    handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
    discord.utils.setup_logging(level=logging.INFO, handler=handler)
    bot.run(os.getenv("TOKEN"))
