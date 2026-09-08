import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

HORSES = ["🐎", "🐴", "🦄", "🐎"]  # 4 horses
TRACK_LENGTH = 20
PAYOUT_MULTIPLIER = 3.5  # flat payout if your horse wins (fair would be 4x for 4 horses)


def render_track(positions: list[int]) -> str:
    lines = []
    for i, pos in enumerate(positions):
        pos = min(pos, TRACK_LENGTH)
        lane = "─" * pos + HORSES[i] + "─" * (TRACK_LENGTH - pos)
        lines.append(f"`{i + 1}` {lane}🏁")
    return "\n".join(lines)


class Horse(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="horse", description="Bet on a horse. Win up to 3.5x your bet.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", horse="Which horse to bet on (1-4)")
    async def horse(self, ctx: commands.Context, bet: str, horse: int):
        if not (1 <= horse <= len(HORSES)):
            await ctx.send(embed=error_embed(f"Pick a horse between 1 and {len(HORSES)}."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        positions = [0] * len(HORSES)
        msg = await ctx.send(embed=base_embed("🏇 Race starting...", render_track(positions), COLOR_PRIMARY))

        winner = None
        while winner is None:
            await asyncio.sleep(0.5)
            for i in range(len(HORSES)):
                positions[i] += random.randint(0, 3)
            leader = max(range(len(HORSES)), key=lambda i: positions[i])
            if positions[leader] >= TRACK_LENGTH:
                winner = leader
            await msg.edit(embed=base_embed("🏇 Racing!", render_track(positions), COLOR_PRIMARY))

        won = winner == (horse - 1)
        payout = int(amount * PAYOUT_MULTIPLIER) if won else 0
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = render_track(positions) + f"\n\n**Horse {winner + 1}** wins the race!\n\n"
        if won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}** ({PAYOUT_MULTIPLIER}x)\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Horse(bot))
