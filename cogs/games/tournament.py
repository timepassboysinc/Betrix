import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, info_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

JOIN_WINDOW_SECONDS = 30


class TournamentView(discord.ui.View):
    def __init__(self, host: discord.Member, entry: int):
        super().__init__(timeout=JOIN_WINDOW_SECONDS)
        self.host = host
        self.entry = entry
        self.joined: dict[int, discord.Member] = {}

    def embed(self, seconds_left: int | None = None):
        names = "\n".join(m.mention for m in self.joined.values()) or "No one yet."
        desc = f"Entry: {fmt(self.entry)}\nPot so far: {fmt(self.entry * len(self.joined))}\n\n**Players:**\n{names}"
        if seconds_left is not None:
            desc += f"\n\nJoin window closes in **{seconds_left}s**."
        return base_embed("🏆 Dice Tournament", desc, COLOR_PRIMARY)

    @discord.ui.button(label="Join", emoji="🎲", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.joined:
            await interaction.response.send_message("You're already in.", ephemeral=True)
            return
        ok = await db.try_take(interaction.user.id, self.entry)
        if not ok:
            await interaction.response.send_message("You don't have enough balance to join.", ephemeral=True)
            return
        self.joined[interaction.user.id] = interaction.user
        await interaction.response.edit_message(embed=self.embed())


class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="tournament", description="Start a dice tournament — anyone can join and compete for the pot.")
    @app_commands.describe(entry="Entry fee per player")
    async def tournament(self, ctx: commands.Context, entry: int):
        if entry <= 0:
            await ctx.send(embed=error_embed("Entry fee must be positive."))
            return

        view = TournamentView(ctx.author, entry)
        ok = await db.try_take(ctx.author.id, entry)
        if not ok:
            await ctx.send(embed=error_embed("You don't have enough balance to start this tournament."))
            return
        view.joined[ctx.author.id] = ctx.author

        msg = await ctx.send(embed=view.embed(JOIN_WINDOW_SECONDS), view=view)

        elapsed = 0
        step = 5
        while elapsed < JOIN_WINDOW_SECONDS:
            await asyncio.sleep(step)
            elapsed += step
            left = JOIN_WINDOW_SECONDS - elapsed
            if left > 0:
                await msg.edit(embed=view.embed(left))

        for c in view.children:
            c.disabled = True

        players = list(view.joined.values())
        if len(players) < 2:
            for pid in view.joined:
                await db.add_balance(pid, entry)  # refund
            await msg.edit(embed=info_embed("Tournament Cancelled", "Not enough players joined — entries refunded."), view=view)
            return

        rolls = {p.id: random.randint(1, 100) for p in players}
        winner_id = max(rolls, key=rolls.get)
        winner = view.joined[winner_id]
        pot = entry * len(players)
        await db.record_result(winner_id, pot, True)
        for p in players:
            if p.id != winner_id:
                await db.record_result(p.id, 0, False)

        roll_lines = "\n".join(f"{view.joined[pid].mention}: **{roll}**" for pid, roll in rolls.items())
        e = win_embed("🏆 Tournament Results", f"{roll_lines}\n\n{winner.mention} wins the pot of **{fmt(pot)}**!")
        e.color = COLOR_GOLD
        await msg.edit(embed=e, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tournament(bot))
