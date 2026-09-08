import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError, Deck, hand_str
from animations import suspense
from config import fmt, win_embed, lose_embed, error_embed, base_embed, info_embed, COLOR_PRIMARY


def baccarat_value(cards) -> int:
    total = 0
    for c in cards:
        if c.rank in ("10", "J", "Q", "K"):
            v = 0
        elif c.rank == "A":
            v = 1
        else:
            v = int(c.rank)
        total += v
    return total % 10


class Baccarat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="baccarat", aliases=["bc"], description="Bet on Player, Banker, or Tie.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", side="player, banker, or tie")
    @app_commands.choices(side=[
        app_commands.Choice(name="Player", value="player"),
        app_commands.Choice(name="Banker", value="banker"),
        app_commands.Choice(name="Tie", value="tie"),
    ])
    async def baccarat(self, ctx: commands.Context, bet: str, side: str):
        side = side.lower()
        if side not in ("player", "banker", "tie"):
            await ctx.send(embed=error_embed("Pick `player`, `banker`, or `tie`."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)

        msg = await ctx.send(embed=base_embed("🎴 Dealing...", f"Bet on **{side}**", COLOR_PRIMARY))
        await suspense(msg, "🎴 Dealing...", f"Bet on **{side}**")

        deck = Deck()
        player_cards = deck.draw(2)
        banker_cards = deck.draw(2)
        p_val = baccarat_value(player_cards)
        b_val = baccarat_value(banker_cards)

        if p_val > b_val:
            winner = "player"
        elif b_val > p_val:
            winner = "banker"
        else:
            winner = "tie"

        if winner == "tie":
            multiplier = 9.0 if side == "tie" else 1.0  # push refund if you bet player/banker
        elif side == winner:
            multiplier = 2.0 if side == "player" else 1.95
        else:
            multiplier = 0.0

        won = multiplier > 1.0
        payout = int(amount * multiplier)
        await db.record_result(ctx.author.id, payout, won)
        new_bal = await db.get_balance(ctx.author.id)

        desc = (
            f"Player: {hand_str(player_cards)} = **{p_val}**\n"
            f"Banker: {hand_str(banker_cards)} = **{b_val}**\n"
            f"Winner: **{winner}**\n\n"
        )
        if multiplier == 1.0:
            e = info_embed("Push — Tie", desc + f"Your bet was refunded.\nBalance: {fmt(new_bal)}")
        elif won:
            e = win_embed("You Won!", desc + f"You won **{fmt(payout)}** ({multiplier}x)\nBalance: {fmt(new_bal)}")
        else:
            e = lose_embed("You Lost", desc + f"You lost **{fmt(amount)}**\nBalance: {fmt(new_bal)}")
        await msg.edit(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Baccarat(bot))
