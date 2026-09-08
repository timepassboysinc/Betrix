import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, info_embed, error_embed, base_embed, COLOR_GOLD, COLOR_PRIMARY

RAIN_LOOKBACK_MESSAGES = 100
RAIN_LOOKBACK_MINUTES = 15
WHEEL_JOIN_SECONDS = 20


async def _find_active_members(channel: discord.abc.Messageable, exclude_id: int, bot_user_id: int) -> list[int]:
    """Looks back through recent channel history for distinct human authors."""
    import datetime
    cutoff = discord.utils.utcnow() - datetime.timedelta(minutes=RAIN_LOOKBACK_MINUTES)
    seen: list[int] = []
    async for message in channel.history(limit=RAIN_LOOKBACK_MESSAGES):
        if message.created_at < cutoff:
            break
        if message.author.bot or message.author.id == exclude_id or message.author.id == bot_user_id:
            continue
        if message.author.id not in seen:
            seen.append(message.author.id)
    return seen


class Rain(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="rain", description="Rain points on active users in this channel.")
    @app_commands.describe(bet="Total amount to rain (or 'half' / 'all')")
    async def rain(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        recipients = await _find_active_members(ctx.channel, ctx.author.id, self.bot.user.id)
        if not recipients:
            await ctx.send(embed=error_embed(
                f"No other active users found in the last {RAIN_LOOKBACK_MINUTES} minutes — nobody to rain on."
            ))
            return

        await db.try_take(ctx.author.id, amount)
        share = amount // len(recipients)
        leftover = amount - share * len(recipients)  # rounding remainder stays with the rainer
        if leftover:
            await db.add_balance(ctx.author.id, leftover)

        for uid in recipients:
            await db.add_balance(uid, share)

        names = ", ".join(f"<@{uid}>" for uid in recipients)
        e = win_embed(
            "🌧️ It's Raining Points!",
            f"{ctx.author.mention} rained **{fmt(amount)}** on the channel!\n"
            f"Each of {len(recipients)} active users got **{fmt(share)}**\n\n{names}",
        )
        await ctx.send(embed=e)


class RainWheelView(discord.ui.View):
    def __init__(self, host: discord.Member, pot: int):
        super().__init__(timeout=WHEEL_JOIN_SECONDS)
        self.host = host
        self.pot = pot
        self.joined: dict[int, discord.Member] = {}

    def embed(self, seconds_left: int | None = None):
        names = "\n".join(m.mention for m in self.joined.values()) or "No one yet."
        desc = f"Host: {self.host.mention}\nPrize pot: **{fmt(self.pot)}**\n\n**In the lobby:**\n{names}"
        if seconds_left is not None:
            desc += f"\n\nJoin window closes in **{seconds_left}s**."
        return base_embed("🎡 Rain Wheel — One Winner Takes All!", desc, COLOR_PRIMARY)

    @discord.ui.button(label="Join", emoji="🎟️", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.bot:
            return
        if interaction.user.id in self.joined:
            await interaction.response.send_message("You're already in the lobby.", ephemeral=True)
            return
        self.joined[interaction.user.id] = interaction.user
        await interaction.response.edit_message(embed=self.embed())


class RainWheel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="rainwheel", description="Open a rain wheel lobby — one lucky winner takes the entire jackpot.")
    @app_commands.describe(bet="Prize pot to put up (or 'half' / 'all')")
    async def rainwheel(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        view = RainWheelView(ctx.author, amount)
        msg = await ctx.send(embed=view.embed(WHEEL_JOIN_SECONDS), view=view)

        elapsed, step = 0, 5
        while elapsed < WHEEL_JOIN_SECONDS:
            await asyncio.sleep(step)
            elapsed += step
            left = WHEEL_JOIN_SECONDS - elapsed
            if left > 0:
                await msg.edit(embed=view.embed(left))

        for c in view.children:
            c.disabled = True

        if not view.joined:
            await db.add_balance(ctx.author.id, amount)  # refund
            await msg.edit(embed=info_embed("Rain Wheel Cancelled", "Nobody joined — pot refunded to host."), view=view)
            return

        winner_id = random.choice(list(view.joined.keys()))
        winner = view.joined[winner_id]
        await db.record_result(winner_id, amount, True)

        e = win_embed("🎉 We Have a Winner!", f"{winner.mention} takes the entire **{fmt(amount)}** pot!")
        e.color = COLOR_GOLD
        await msg.edit(embed=e, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Rain(bot))
    await bot.add_cog(RainWheel(bot))
