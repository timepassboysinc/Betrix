"""
Shared animation helper so games don't each reinvent a bare 'await asyncio.sleep(1)'.
Renders a filling progress bar under the title while a result is being decided.
"""
import asyncio

import discord

from config import base_embed, COLOR_PRIMARY

BAR_LENGTH = 12
FILLED = "▰"
EMPTY = "▱"


async def suspense(msg: discord.Message, title: str, subtitle: str = "", color: int = COLOR_PRIMARY,
                    frames: int = 6, delay: float = 0.25):
    """Edits `msg` repeatedly with a filling progress bar for a bit of drama before the result lands."""
    for i in range(1, frames + 1):
        filled_count = round(BAR_LENGTH * i / frames)
        bar = FILLED * filled_count + EMPTY * (BAR_LENGTH - filled_count)
        body = f"{subtitle}\n\n`{bar}`" if subtitle else f"`{bar}`"
        await msg.edit(embed=base_embed(title, body, color))
        await asyncio.sleep(delay)
