import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, E_DICE

HOUSE_EDGE = 0.02


def probability_over_under(num_dice: int, target: int, direction: str) -> float:
    """Brute-force probability by enumerating all outcomes (num_dice is small, 2-5)."""
    from itertools import product
    total_outcomes = 0
    favorable = 0
    for combo in product(range(1, 7), repeat=num_dice):
        total_outcomes += 1
        s = sum(combo)
        if (direction == "under" and s < target) or (direction == "over" and s > target):
            favorable += 1
    return favorable / total_outcomes if total_outcomes else 0


class CrazyDice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="crazydice", aliases=["cdice"], description="Bet on the sum of multiple dice landing over or under a target.")
    @app_commands.describe(
        bet="Amount to bet (or 'half' / 'all')",
        dice_count="How many dice to roll (2-5)",
        target="Target sum to bet against",
        direction="Whether you win if the sum is over or under your target",
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="Under", value="under"),
        app_commands.Choice(name="Over", value="over"),
    ])
    async def crazydice(self, ctx: commands.Context, bet: str, dice_count: int, target: int, direction: str):
        if not (2 <= dice_count <= 5):
            await ctx.send(embed=error_embed("Dice count must be between 2 and 5."))
            return
        lo, hi = dice_count, dice_count * 6
        if not (lo < target < hi):
            await ctx.send(embed=error_embed(f"With {dice_count} dice, target must be between {lo + 1} and {hi - 1}."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        win_chance = probability_over_under(dice_count, target, direction)
        if win_chance <= 0:
            await ctx.send(embed=error_embed("That bet can never win — pick a different target."))
            return
        multiplier = round((1 / win_chance) * (1 - HOUSE_EDGE), 4)

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed(f"{E_DICE} Rolling {dice_count} dice...", f"Betting **{direction} {target}**", COLOR_PRIMARY))
        await suspense(msg, f"{E_DICE} Rolling {dice_count} dice...", f"Betting **{direction} {target}**")

        rolls = [random.randint(1, 6) for _ in range(dice_count)]
        total = sum(rolls)
        won = (total < target) if direction == "under" else (total > target)
        payout = int(amount * multiplier) if won else 0
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = f"Rolled {rolls} = **{total}** (needed {direction} {target})\nMultiplier: {multiplier}x\n"
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(CrazyDice(bot))
