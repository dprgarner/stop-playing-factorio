import os
import logging

import discord
from dotenv import load_dotenv

from stop_playing_factorio.game_watch_bot import GameWatchBot
from stop_playing_factorio.relative_notifications import FACTORIO_RELATIVE_NOTIFICATIONS


def main() -> None:
    load_dotenv()
    bot = GameWatchBot(
        game="Factorio", relative_notifications=FACTORIO_RELATIVE_NOTIFICATIONS
    )
    handler = logging.FileHandler(filename="spfbot.log", encoding="utf-8", mode="a")
    discord.utils.setup_logging(level=logging.INFO, handler=handler)
    bot.run(os.getenv("TOKEN"))


if __name__ == "__main__":
    main()
