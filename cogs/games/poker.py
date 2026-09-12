from collections import Counter
import io

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from utils import resolve_bet, BetError, Deck, Card, hand_str
from imaging import render_single_hand
from config import fmt, win_embed, lose_embed, error_embed, base_embed, COLOR_PRIMARY, COLOR_GOLD

VALUE_MAP = {"A": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13}

PAYTABLE = [
    ("Royal Flush", 250),
    ("Straight Flush", 50),
    ("Four of a Kind", 25),
    ("Full House", 9),
    ("Flush", 6),
    ("Straight", 4),
    ("Three of a Kind", 3),
    ("Two Pair", 2),
    ("Jacks or Better", 1),
]


def evaluate_hand(cards: list[Card]) -> tuple[str, float]:
    values = sorted(VALUE_MAP[c.rank] for c in cards)
    suits = {c.suit for c in cards}
    ranks = [c.rank for c in cards]
    counts = sorted(Counter(ranks).values(), reverse=True)

    is_flush = len(suits) == 1
    is_broadway = values == [1, 10, 11, 12, 13]
    is_straight = is_broadway or values == list(range(values[0], values[0] + 5))

    if is_straight and is_flush:
        return ("Royal Flush", 250) if is_broadway else ("Straight Flush", 50)
    if counts[0] == 4:
        return "Four of a Kind", 25
    if counts[0] == 3 and counts[1] == 2:
        return "Full House", 9
    if is_flush:
        return "Flush", 6
    if is_straight:
        return "Straight", 4
    if counts[0] == 3:
        return "Three of a Kind", 3
    if counts[0] == 2 and counts[1] == 2:
        return "Two Pair", 2
    if counts[0] == 2:
        pair_rank = [r for r, c in Counter(ranks).items() if c == 2][0]
        if pair_rank in ("J", "Q", "K", "A"):
            return "Jacks or Better", 1
    return "High Card", 0


class HoldButton(discord.ui.Button):
    def __init__(self, index: int, card: Card):
        super().__init__(style=discord.ButtonStyle.secondary, label=f"{card} - Hold", row=0)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: "PokerView" = self.view
        view.held[self.index] = not view.held[self.index]
        self.style = discord.ButtonStyle.success if view.held[self.index] else discord.ButtonStyle.secondary
        card = view.hand[self.index]
        self.label = f"{card} {'HELD' if view.held[self.index] else '- Hold'}"
        await interaction.response.edit_message(view=view)


class DrawButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Draw", emoji="🃏", row=1)

    async def callback(self, interaction: discord.Interaction):
        await self.view.draw(interaction)


class PokerView(discord.ui.View):
    def __init__(self, ctx: commands.Context, deck: Deck, hand: list[Card], bet: int):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.deck = deck
        self.hand = hand
        self.bet = bet
        self.held = [False] * 5
        for i, card in enumerate(hand):
            self.add_item(HoldButton(i, card))
        self.add_item(DrawButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def _image_file(self, label: str = "YOUR HAND") -> discord.File:
        img_bytes = render_single_hand(label, [str(c) for c in self.hand])
        return discord.File(io.BytesIO(img_bytes), filename="poker.png")

    async def draw(self, interaction: discord.Interaction):
        for i in range(5):
            if not self.held[i]:
                self.hand[i] = self.deck.draw(1)[0]

        name, multiplier = evaluate_hand(self.hand)
        payout = int(self.bet * multiplier)
        won = payout > 0
        await db.record_result(self.ctx.author.id, payout, won)
        new_bal = await db.get_balance(self.ctx.author.id)

        for c in self.children:
            c.disabled = True

        desc = f"**{name}**\n\n"
        if won:
            e = win_embed("You Won!", desc + f"Payout: {multiplier}x — You won **{fmt(payout)}**\nBalance: {fmt(new_bal)}")
            if multiplier >= 25:
                e.color = COLOR_GOLD
        else:
            e = lose_embed("No Win", desc + f"You lost **{fmt(self.bet)}**\nBalance: {fmt(new_bal)}")
        file = self._image_file("FINAL HAND")
        e.set_image(url="attachment://poker.png")
        await interaction.response.edit_message(embed=e, view=self, attachments=[file])
        self.stop()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class Poker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="poker", aliases=["pk"], description="Solo video poker — Jacks or Better.")
    @app_commands.describe(bet="Amount to bet (or 'half' / 'all')")
    async def poker(self, ctx: commands.Context, bet: str):
        try:
            amount = await resolve_bet(ctx.author.id, bet)
        except BetError as e:
            await ctx.send(embed=error_embed(str(e)))
            return

        await db.try_take(ctx.author.id, amount)
        deck = Deck()
        hand = deck.draw(5)

        table = "\n".join(f"{name}: {mult}x" for name, mult in PAYTABLE)
        e = base_embed(
            "🃏 Video Poker",
            f"Tap cards to **hold**, then hit **Draw**.\n\n**Paytable**\n{table}",
            COLOR_PRIMARY,
        )
        view = PokerView(ctx, deck, hand, amount)
        file = view._image_file("YOUR HAND")
        e.set_image(url="attachment://poker.png")
        await ctx.send(embed=e, file=file, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Poker(bot))
