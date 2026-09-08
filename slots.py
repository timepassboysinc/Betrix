import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

# symbol: (weight, payout multiplier for 3-of-a-kind)
SYMBOLS = {
    "🍒": (30, 1.5),
    "🍋": (24, 2),
    "🍇": (18, 3),
    "🔔": (12, 5),
    "⭐": (8, 10),
    "💎": (5, 25),
    "7️⃣": (3, 50),
}
PAIR_MULT = 0.5  # any two matching pays half that symbol's multiplier

WEIGHTED_POOL = [s for s, (w, _) in SYMBOLS.items() for _ in range(w)]


def spin_reel() -> str:
    return random.choice(WEIGHTED_POOL)


def render(reels: list[str]) -> str:
    return f"┃ {reels[0]} ┃ {reels[1]} ┃ {reels[2]} ┃"


class Slots(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="slots", aliases=["sl"], description="Spin 3 reels for a jackpot.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def slots(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed("🎰 Spinning...", render([spin_reel() for _ in range(3)]), COLOR_PRIMARY))
        for _ in range(5):
            await asyncio.sleep(0.3)
            await msg.edit(embed=base_embed("🎰 Spinning...", render([spin_reel() for _ in range(3)]), COLOR_PRIMARY))

        final = [spin_reel() for _ in range(3)]
        multiplier = 0.0
        result_text = "No match."
        if final[0] == final[1] == final[2]:
            multiplier = SYMBOLS[final[0]][1]
            result_text = f"JACKPOT! Triple {final[0]}"
        elif final[0] == final[1] or final[1] == final[2] or final[0] == final[2]:
            matched = final[1] if final[0] == final[1] or final[1] == final[2] else final[0]
            multiplier = SYMBOLS[matched][1] * PAIR_MULT
            result_text = f"Pair of {matched}"

        won = multiplier > 0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        board = render(final)
        if won:
            e = win_embed("Winner!", f"{board}\n\n{result_text} ({multiplier}x)\nYou won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 20:
                e.color = COLOR_GOLD
                e.title = "🎉 JACKPOT!"
        else:
            e = lose_embed("No Luck", f"{board}\n\n{result_text}\nYou lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Slots(bot))
