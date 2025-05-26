from datetime import datetime, timedelta
import logging
from typing import Optional

import discord
from openai import OpenAI
import pytz

from stop_playing_factorio.db.game_sessions import GameSession
from stop_playing_factorio.llm.core import CORE_CONTEXT, MODEL, get_instructions

logger = logging.getLogger()


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
) -> list[object]:
    client = OpenAI()
    instructions = get_instructions(user, True)
    nudge_prompt = get_nudge_prompt(game_session)
    logger.info(f"nudge_prompt: {nudge_prompt}")

    user_exchange += [{"role": "user", "content": nudge_prompt}]
    response = client.responses.create(
        model=MODEL,
        instructions=instructions,
        input=user_exchange,
        temperature=1.0,
    )
    if not response.output_text:
        raise Exception("No output text received from OpenAI API")

    logger.info(f"response from OpenAI API: {response.output_text}")
    return user_exchange + [{"role": "assistant", "content": response.output_text}]
