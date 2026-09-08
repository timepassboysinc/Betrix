import asyncio
import io
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from imaging import render_dice_roll
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, E_DICE

HOUSE_EDGE = 0.01  # 1%


class Dice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="dice", aliases=["dc"], description="Bet on a 1-100 roll landing over or under your number.")
    @app_commands.describe(
        bet="Amount to bet (or 'half' / 'all')",
        target="Number 2-98 to bet against",
        direction="Whether you win if the roll is over or under your target",
    )
    @app_commands.choices(direction=[
        app_commands.Choice(name="Under", value="under"),
        app_commands.Choice(name="Over", value="over"),
    ])
    async def dice(self, ctx: commands.Context, bet: str, target: int, direction: str):
        if not (2 <= target <= 98):
            await ctx.send(embed=error_embed("Target must be between 2 and 98."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        win_chance = target if direction == "under" else (100 - target)
        multiplier = round((100 / win_chance) * (1 - HOUSE_EDGE), 4)

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed(f"{E_DICE} Rolling...", f"Betting **{direction} {target}**", COLOR_PRIMARY))
        for _ in range(3):
            await asyncio.sleep(0.35)
            spin = random.randint(1, 100)
            await msg.edit(embed=base_embed(f"{E_DICE} Rolling... {spin}", f"Betting **{direction} {target}**", COLOR_PRIMARY))

        roll = random.randint(1, 100)
        won = (roll < target) if direction == "under" else (roll > target)
        payout = int(amount * multiplier) if won else 0
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = f"Rolled **{roll}** (needed {direction} {target})\nMultiplier: {multiplier}x\n"
        img_bytes = render_dice_roll(roll)
        file = discord.File(io.BytesIO(img_bytes), filename="dice.png")
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        e.set_thumbnail(url="attachment://dice.png")
        await msg.edit(embed=e, attachments=[file])


async def setup(bot: commands.Bot):
    await bot.add_cog(Dice(bot))
