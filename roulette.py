import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
POCKETS = [str(n) for n in range(0, 37)] + ["00"]

COLUMN_1 = {n for n in range(1, 37) if n % 3 == 1}
COLUMN_2 = {n for n in range(1, 37) if n % 3 == 2}
COLUMN_3 = {n for n in range(1, 37) if n % 3 == 0}


def pocket_color(pocket: str) -> str:
    if pocket in ("0", "00"):
        return "green"
    return "red" if int(pocket) in RED_NUMBERS else "black"


def evaluate(bet_on: str, pocket: str) -> float:
    """Returns payout multiplier (0 if lost) for a given bet space and landed pocket."""
    bet_on = bet_on.lower().strip()
    color = pocket_color(pocket)

    if bet_on in ("red", "black"):
        return 2.0 if color == bet_on else 0.0
    if bet_on in ("odd", "even"):
        if pocket in ("0", "00"):
            return 0.0
        n = int(pocket)
        is_even = n % 2 == 0
        return 2.0 if (bet_on == "even") == is_even else 0.0
    if bet_on in ("low", "1-18"):
        return 2.0 if pocket not in ("0", "00") and 1 <= int(pocket) <= 18 else 0.0
    if bet_on in ("high", "19-36"):
        return 2.0 if pocket not in ("0", "00") and 19 <= int(pocket) <= 36 else 0.0
    if bet_on in ("col1", "column1"):
        return 3.0 if pocket not in ("0", "00") and int(pocket) in COLUMN_1 else 0.0
    if bet_on in ("col2", "column2"):
        return 3.0 if pocket not in ("0", "00") and int(pocket) in COLUMN_2 else 0.0
    if bet_on in ("col3", "column3"):
        return 3.0 if pocket not in ("0", "00") and int(pocket) in COLUMN_3 else 0.0
    if bet_on in POCKETS:
        return 36.0 if bet_on == pocket else 0.0
    return -1.0  # invalid


class Roulette(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="roulette", aliases=["rl"], description="Play American roulette.")
    @app_commands.describe(
        bet="Amount to bet (or 'half' / 'all')",
        space="red, black, odd, even, low, high, col1, col2, col3, or a number (0-36, 00)",
    )
    async def roulette(self, ctx: commands.Context, bet: str, space: str):
        multiplier_check = evaluate(space, "1")  # dummy check just to validate the space string
        if multiplier_check == -1.0 and space.lower() not in POCKETS:
            await ctx.send(embed=error_embed(
                "Invalid bet space. Use: red, black, odd, even, low, high, col1, col2, col3, or a number 0-36 / 00."
            ))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed("🎡 Spinning the wheel...", f"Bet on **{space}**", COLOR_PRIMARY))
        for _ in range(4):
            await asyncio.sleep(0.35)
            await msg.edit(embed=base_embed(f"🎡 {random.choice(POCKETS)}...", f"Bet on **{space}**", COLOR_PRIMARY))

        pocket = random.choice(POCKETS)
        multiplier = evaluate(space, pocket)
        won = multiplier > 0
        payout = int(amount * multiplier) if won else 0
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        color = pocket_color(pocket)
        desc = f"Ball landed on **{pocket}** ({color})\n"
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}** ({multiplier}x)\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Roulette(bot))
