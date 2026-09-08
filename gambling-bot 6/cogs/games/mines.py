import math
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY

ROWS, COLS = 4, 5
TOTAL_TILES = ROWS * COLS
HOUSE_EDGE = 0.02


def fair_multiplier(n: int, m: int, k: int) -> float:
    """n tiles total, m mines, k safe tiles revealed so far."""
    mult = 1.0
    for i in range(k):
        mult *= (n - i) / (n - m - i)
    return round(mult * (1 - HOUSE_EDGE), 4)


class TileButton(discord.ui.Button):
    def __init__(self, index: int, row: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=row)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.reveal(interaction, self.index, self)


class CashOutButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="Cash Out", emoji="💰", row=4)

    async def callback(self, interaction: discord.Interaction):
        await self.view.cash_out(interaction)


class MinesView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bet: int, mine_count: int):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bet = bet
        self.mine_count = mine_count
        self.mines = set(random.sample(range(TOTAL_TILES), mine_count))
        self.revealed = set()
        self.tile_buttons: list[TileButton] = []
        self.over = False

        for i in range(TOTAL_TILES):
            btn = TileButton(i, row=i // COLS)
            self.tile_buttons.append(btn)
            self.add_item(btn)
        self.cash_button = CashOutButton()
        self.cash_button.disabled = True
        self.add_item(self.cash_button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def current_multiplier(self) -> float:
        return fair_multiplier(TOTAL_TILES, self.mine_count, len(self.revealed))

    def embed(self, footer: str = "") -> discord.Embed:
        mult = self.current_multiplier()
        desc = (
            f"Mines: **{self.mine_count}** | Safe tiles found: **{len(self.revealed)}**\n"
            f"Current multiplier: **{mult}x** (would win {fmt(int(self.bet * mult))})\n"
            f"Bet: {fmt(self.bet)}"
        )
        if footer:
            desc += f"\n\n{footer}"
        return base_embed("💣 Mines", desc, COLOR_PRIMARY)

    def reveal_all(self):
        for btn in self.tile_buttons:
            btn.disabled = True
            if btn.index in self.mines:
                btn.style = discord.ButtonStyle.danger
                btn.emoji = "💣"
            elif btn.index in self.revealed:
                btn.style = discord.ButtonStyle.success
                btn.emoji = "💎"
            else:
                btn.style = discord.ButtonStyle.secondary
                btn.emoji = "⬛"
        self.cash_button.disabled = True

    async def reveal(self, interaction: discord.Interaction, index: int, btn: TileButton):
        if self.over or index in self.revealed:
            await interaction.response.defer()
            return

        if index in self.mines:
            self.over = True
            self.reveal_all()
            await db.record_result(self.ctx.author.id, 0, False)
            new_bal = await db.get_balance(self.ctx.author.id)
            await interaction.response.edit_message(
                embed=lose_embed("💥 Boom! You hit a mine.", f"You lost **{fmt(self.bet)}**\nBalance: {fmt(new_bal)}"),
                view=self,
            )
            self.stop()
            return

        self.revealed.add(index)
        btn.style = discord.ButtonStyle.success
        btn.emoji = "💎"
        btn.disabled = True
        self.cash_button.disabled = False

        if len(self.revealed) == TOTAL_TILES - self.mine_count:
            # cleared the whole board
            await self.cash_out(interaction)
            return

        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def cash_out(self, interaction: discord.Interaction):
        if self.over:
            return
        self.over = True
        mult = self.current_multiplier()
        payout = int(self.bet * mult)
        self.reveal_all()
        await db.record_result(self.ctx.author.id, payout, True)
        new_bal = await db.get_balance(self.ctx.author.id)
        await interaction.response.edit_message(
            embed=win_embed(f"Cashed Out at {mult}x!", f"You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}"),
            view=self,
        )
        self.stop()

    async def on_timeout(self):
        if not self.over:
            self.reveal_all()


class Mines(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="mines", aliases=["mn"], description="Reveal tiles, avoid the mines, cash out anytime.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')", mines="Number of mines (1-15)")
    async def mines(self, ctx: commands.Context, bet: str, mines: int = 3):
        if not (1 <= mines <= 15):
            await ctx.send(embed=error_embed("Mines must be between 1 and 15."))
            return
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        view = MinesView(ctx, amount, mines)
        await ctx.send(embed=view.embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Mines(bot))
