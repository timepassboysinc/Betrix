import time
import io

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from imaging import render_balance_card
from config import (
    fmt, base_embed, info_embed, error_embed, win_embed,
    CURRENCY_NAME, DAILY_AMOUNT, DAILY_COOLDOWN_HOURS,
    COLOR_GOLD, E_TROPHY, E_CROWN, E_COIN, E_CHECK,
)


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", aliases=["bal", "b"], description=f"Check your {CURRENCY_NAME} balance.")
    @app_commands.describe(member="Whose balance to check (optional)")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        bal = await db.get_balance(member.id)
        avatar_bytes = await member.display_avatar.replace(size=256).read()
        image_bytes = render_balance_card(member.display_name, member.id, avatar_bytes, bal)
        file = discord.File(io.BytesIO(image_bytes), filename="balance.png")
        e = info_embed(f"{member.display_name}'s Balance", f"**{fmt(bal)}**")
        e.set_image(url="attachment://balance.png")
        await ctx.send(embed=e, file=file)

    @commands.hybrid_command(name="daily", aliases=["d"], description=f"Claim your free daily {CURRENCY_NAME}.")
    async def daily(self, ctx: commands.Context):
        last = await db.get_last_daily(ctx.author.id)
        now = time.time()
        cooldown = DAILY_COOLDOWN_HOURS * 3600
        remaining = cooldown - (now - last)
        if remaining > 0:
            hrs = int(remaining // 3600)
            mins = int((remaining % 3600) // 60)
            await ctx.send(embed=error_embed(f"Already claimed. Come back in **{hrs}h {mins}m**."))
            return
        await db.add_balance(ctx.author.id, DAILY_AMOUNT)
        await db.set_last_daily(ctx.author.id, now)
        new_bal = await db.get_balance(ctx.author.id)
        e = win_embed("Daily Reward Claimed!", f"You received **{fmt(DAILY_AMOUNT)}**\nNew balance: {fmt(new_bal)}")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Top 10 richest gamblers.")
    async def leaderboard(self, ctx: commands.Context):
        rows = await db.get_leaderboard(10)
        if not rows:
            await ctx.send(embed=info_embed("Leaderboard", "Nobody has any points yet."))
            return
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, bal) in enumerate(rows):
            user = ctx.guild.get_member(user_id) if ctx.guild else None
            name = user.display_name if user else f"<@{user_id}>"
            prefix = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{name}** — {fmt(bal)}")
        e = base_embed(f"{E_TROPHY} Leaderboard", "\n".join(lines), COLOR_GOLD)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="stats", aliases=["st"], description="View your (or someone's) gambling stats.")
    @app_commands.describe(member="Whose stats to check (optional)")
    async def stats(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        s = await db.get_stats(member.id)
        total_games = s["wins"] + s["losses"]
        wr = (s["wins"] / total_games * 100) if total_games else 0
        e = info_embed(f"{E_CROWN} {member.display_name}'s Stats")
        e.add_field(name="Balance", value=fmt(s["balance"]))
        e.add_field(name="Net Profit", value=fmt(s["net_profit"]))
        e.add_field(name="Total Wagered", value=fmt(s["wagered"]))
        e.add_field(name="Wins", value=str(s["wins"]))
        e.add_field(name="Losses", value=str(s["losses"]))
        e.add_field(name="Win Rate", value=f"{wr:.1f}%")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="tip", aliases=["t"], description=f"Give some of your {CURRENCY_NAME} to another user.")
    @app_commands.describe(member="Who to tip", amount="How much to send")
    async def tip(self, ctx: commands.Context, member: discord.Member, amount: int):
        if member.bot:
            await ctx.send(embed=error_embed("You can't tip a bot."))
            return
        if member.id == ctx.author.id:
            await ctx.send(embed=error_embed("You can't tip yourself."))
            return
        if amount <= 0:
            await ctx.send(embed=error_embed("Amount must be positive."))
            return
        ok = await db.try_take(ctx.author.id, amount)
        if not ok:
            await ctx.send(embed=error_embed("You don't have enough balance."))
            return
        await db.add_balance(member.id, amount)
        e = win_embed("Tip Sent", f"{ctx.author.mention} sent **{fmt(amount)}** to {member.mention} {E_CHECK}")
        await ctx.send(embed=e)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
