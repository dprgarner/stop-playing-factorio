import discord
from openai import OpenAI

from stop_playing_factorio.llm.core import MODEL, get_instructions, logger


def get_bot_response(
    user: discord.User, is_in_game_session: bool, user_exchange: list[object]
):
    client = OpenAI()
    instructions = get_instructions(user, is_in_game_session)

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
