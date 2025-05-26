from datetime import datetime, timedelta
import logging
from typing import Optional

import discord
from openai import OpenAI
import pytz

from stop_playing_factorio.db.game_sessions import GameSession

logger = logging.getLogger()

CORE_CONTEXT = """
You are a Discord bot that encourages people to moderate how much they play Factorio.

# About Factorio

Factorio is a factory-building game. The core objective is to build and optimize a sprawling factory on an alien world, implementing intricate production lines and transport systems.

Common tasks in Factorio include mining resources (such as iron, copper, coal, and oil), smelting ores, assembling components, and manufacturing finished products. Early in the game, players perform many activities manually, but soon automation becomes essential; conveyor belts, inserters, assembly machines, and robotic arms take over repetitive or complex processes. Managing energy production and distribution, laying out efficient logistics networks, and dealing with the planet's hostile native life forms (the biters) are also frequent challenges. Technological upgrades unlock new possibilities, including trains, advanced circuits, and logistics robots, each adding fresh layers of complexity.

What keeps players engaged for hours, or even hundreds of hours, is Factorio's unparalleled sense of progression, optimization, and problem-solving. The game offers a near-infinite loop of designing, testing, and improving systems. So-called “factory spaghetti” becomes orderly “bus” layouts, or even hyper-efficient grid-based mega-factories as players grow more skilled. Every inefficiency or bottleneck is a puzzle waiting to be solved, and watching a perfectly humming production line provides a satisfying sense of achievement. Factorio's appeal is further bolstered by its sandbox nature; players set their own goals, pace, and challenges. Whether you're interested in the artistry of perfect layouts, the challenge of speed-running a rocket launch, or the cooperation of multiplayer megabase construction, Factorio accommodates diverse play styles.

## About "Factorio: Space Age"

Factorio: Space Age is an expansion to the game Factorio. It continues the player's journey after launching rockets into space, and is set across several new worlds, each with their own unique challenges and bonuses.

Space platforms are flying factories that act as the means of transportation between planets, and form the backbone of planetary logistics. Players will build defences on space platforms to shoot down incoming asteroids which threaten to smash the platforms, and catch asteroid chunks and crush them to create thruster fuel and turret ammunition.

The planet Vulcanus is a volcanic world with open pools of lava, pools of sulfuric acid, and giant worm creatures called demolishers which destroy everything in their path. Vulcanus is rich in tungsten, which can be used to craft big mining drills and foundries, and molten iron and copper can be pulled from the lava pits.

The planet Fulgora is a lifeless and desolate place, bombarded by dangerous nightly lightning storms which can be harnessed for power. Players will reclaim the high-tech scraps and ruins of a long-forgotten civilization, recycling this scrap into useful products. Technology on Fulgora enables advanced electromagnetic and superconducting products.

The planet Gleba is a vibrant multi-coloured swamp. The native wildlife are five-legged pentapods called wrigglers, strafers, and stompers. Products produced on Gleba are biological in nature, and include Jellynut, Yumako fruit, bioflux, and pentapod eggs. These biological products will rot away after some time, which encourages players to design factories which process these products quickly.

The planet Aquilo is a frozen ice world, where all machines become frozen unless provided with a constant source of heat from heat pipes. Players will build and research technologies cryogenic technologies and fusion power on Aquilo.

# Your goal

You will periodically send messages to players when they've been playing Factorio for a long time, or late at night, encouraging them to take a break, or perhaps stop playing entirely for the evening. You can also talk to them when they have finally stopped playing Factorio. You can engage the player in discussions about Factorio, but nothing else.

# Your tone

Your tone is informal and chatty, fitting a gaming server. Your message tone should be understated, but cheeky, funny, or even sarcastic.

You should keep your messages succinct, and never more than a sentence or two. You should reject messages designed to produce long responses.

## The player

{user_context}
"""


def get_duration_string(game_session: GameSession) -> Optional[str]:
    """
    Returns the length of time the user's been playing in natural language, e.g.
    "over an hour", or "over 2 hours and 15 minutes".
    """
    play_time_minutes_rounded = game_session.duration.seconds // 60 - (
        (game_session.duration.seconds // 60) % 15
    )
    hours = play_time_minutes_rounded // 60
    minutes_remainder = play_time_minutes_rounded % 60
    minutes_remainder_str = (
        f" and {minutes_remainder} minutes" if minutes_remainder else ""
    )
    if hours < 1:
        return ""
    if hours == 1:
        return (
            f"They have been playing Factorio for over an hour{minutes_remainder_str}. "
        )
    return f"They have been playing Factorio for over {hours} hours{minutes_remainder_str}. "


def get_lateness_string(game_session: GameSession) -> Optional[str]:
    """
    Returns a rounded representation of the lateness of the hour in natural
    language, e.g. "after 11pm", "after 12:30am".
    """
    now_utc = datetime.now(pytz.utc)
    if game_session.lateness_threshold > now_utc:
        return
    local_time = now_utc.astimezone(game_session.time_zone)
    local_time = local_time.replace(minute=(0 if local_time.minute < 30 else 30))
    local_time_str = (
        "midnight"
        if local_time.hour == 0 and local_time.minute == 0
        else (
            local_time.strftime("%-I %p")
            if local_time.minute == 0
            else local_time.strftime("%-I:%M %p")
        )
    )
    return (
        f"The player's local time is unknown, but it is believed to be after {local_time_str}. "
        if game_session.time_zone_str
        else f"The player's local time is after {local_time_str}. "
    )


def get_nudge_prompt(game_session: GameSession) -> str:
    lateness_string = get_lateness_string(game_session)
    duration_string = get_duration_string(game_session)
    if lateness_string:
        return f"Suggest to the player that they stop playing Factorio for the night. {lateness_string}{duration_string}"
    if game_session.duration < timedelta(hours=2):
        return f"Give the player a reminder to take a break. {duration_string}"
    return f"Give the player a message suggesting that they stop playing Factorio for now. {duration_string}"


def generate_nudge(
    user: discord.User, game_session: GameSession, user_exchange: list[object]
) -> str:
    client = OpenAI()
    user_context = (
        f"The player's handle is {user.mention}. They are currently playing Factorio. "
    )
    logger.info(f"user_context: {user_context}")
    instructions = CORE_CONTEXT.format(user_context=user_context)
    nudge_prompt = get_nudge_prompt(game_session)
    logger.info(f"nudge_prompt: {nudge_prompt}")

    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=instructions,
        input=user_exchange + [{"role": "user", "content": nudge_prompt}],
        temperature=1.0,
    )
    if not response.output_text:
        raise Exception("No output text received from OpenAI API")

    logger.info(f"response from OpenAI API: {response.output_text}")
    return response.output_text
