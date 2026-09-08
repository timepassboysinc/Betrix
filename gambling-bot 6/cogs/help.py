import discord
from discord.ext import commands

from permissions import member_is_casino_admin
from config import base_embed, COLOR_PRIMARY, BOT_NAME, CURRENCY_NAME, E_SPARKLE

CATEGORIES = {
    "economy": {
        "label": "💰 Economy",
        "desc": f"Manage your {CURRENCY_NAME}",
        "commands": [
            ("balance [user] (.b)", f"Check your (or someone's) {CURRENCY_NAME} balance."),
            ("daily (.d)", "Claim your free daily reward."),
            ("leaderboard (.lb)", "Top 10 richest players."),
            ("stats [user] (.st)", "View gambling stats — wins, losses, win rate."),
            ("tip <user> <amount> (.t)", "Send points to another player."),
            ("rain <amount>", "Rain points on active users in the channel."),
            ("rainwheel <amount>", "Open a lobby — one random winner takes the whole pot."),
        ],
    },
    "games": {
        "label": "🎮 Games",
        "desc": "All the ways to gamble your points away",
        "commands": [
            ("coinflip <bet> <heads/tails> (.cf)", "Classic 50/50, ~1.92x payout."),
            ("dice <bet> <1-100> <over/under> (.dc)", "Roll under or over your number."),
            ("slots <bet> (.sl)", "Spin 3 reels for a jackpot."),
            ("blackjack <bet> (.bj)", "Play vs the dealer. Hit, Stand, Double."),
            ("crash <bet> (.cr)", "Cash out before the rocket explodes."),
            ("limbo <bet> <target> (.lm)", "Predict the multiplier ceiling."),
            ("mines <bet> <mines> (.mn)", "Reveal tiles, avoid the bombs."),
            ("roulette <bet> <space> (.rl)", "Red/Black/Odd/Even/Number/Column."),
            ("plinko <bet> (.pl)", "Drop a ball through the peg pyramid."),
            ("keno <bet> <numbers...> (.kn)", "Pick numbers, match the draw."),
            ("poker <bet> (.pk)", "Solo video poker — draw your best hand."),
            ("rps @user <bet>", "Rock-paper-scissors for points."),
            ("connect4 @user <bet> (.c4)", "Connect 4 against another player."),
            ("ttt @user <bet>", "Tic-tac-toe against another player."),
            ("blackjackpvp @user <bet> (.bjpvp)", "Blackjack against another player. Winner takes the pot."),
            ("fight <bet> [@user]", "Fight another player, or the house if no one's tagged."),
            ("baccarat <bet> <player/banker/tie> (.bc)", "Bet on the outcome of the hands."),
            ("hilo <bet>", "Guess higher/lower to chain a multiplier."),
            ("horse <bet> <horse 1-4>", "Bet on a horse. Win up to 3.5x."),
            ("case <bet>", "Open a case for a random item multiplier."),
            ("balloon <bet>", "Pump the balloon, cash out before it pops."),
            ("rat <bet>", "Find the hidden rat in a 3x3 grid — 3 attempts."),
            ("classicslots <bet> (.cslots)", "Classic 3-disc slots."),
            ("crazydice <bet> <dice> <target> <over/under> (.cdice)", "Bet on the sum of multiple dice."),
            ("diamonds <bet>", "Spin to match diamonds."),
            ("dicewar <bet>", "Roll a die against the house."),
            ("gtn <bet> <guess>", "Guess the secret number 1-20."),
            ("jackpotwheel <bet> (.jw)", "Bigger bets = bigger slice of the wheel."),
            ("match <bet>", "Reveal 9 tiles, match 3 multipliers to win."),
            ("slide <bet> <target>", "Win if the slider lands on or above your target."),
            ("tight <bet>", "Random multiplier, always 96% RTP."),
            ("tournament <entry>", "Open dice tournament — anyone can join."),
            ("blackjackdice <bet> (.bjdice)", "Blackjack, but with dice instead of cards."),
            ("progressivecoinflip <bet> (.pcf)", "Chain coin flips for an exponential multiplier."),
            ("cards <bet>", "Draw a card — payout depends on the rank."),
        ],
    },
    "admin": {
        "label": "🛠️ Admin",
        "desc": "Server management tools",
        "commands": [
            ("give <user> <amount> (.g)", f"Grant {CURRENCY_NAME} to a user."),
            ("remove <user> <amount> (.rm)", f"Take {CURRENCY_NAME} from a user."),
            ("setbalance <user> <amount> (.sb)", "Set an exact balance."),
            ("giveall <amount> (.ga)", "Give every member in the server points."),
            ("removeall <amount> (.ra)", "Remove points from every member in the server."),
            ("resetbalance <user> (.rb)", "Reset a user to the starting balance."),
        ],
    },
}


def visible_categories(is_admin: bool) -> dict:
    if is_admin:
        return CATEGORIES
    return {k: v for k, v in CATEGORIES.items() if k != "admin"}


def home_embed(is_admin: bool):
    e = base_embed(
        f"{E_SPARKLE} {BOT_NAME} — Help Menu",
        f"Welcome to **{BOT_NAME}**, your server's private casino.\n\n"
        f"Pick a category below to see commands.\n"
        f"All currency is virtual — for fun and bragging rights only.",
        COLOR_PRIMARY,
    )
    for key, cat in visible_categories(is_admin).items():
        e.add_field(name=cat["label"], value=cat["desc"], inline=True)
    return e


def category_embed(key: str):
    cat = CATEGORIES[key]
    lines = [f"`{cmd}` — {desc}" for cmd, desc in cat["commands"]]
    return base_embed(f"{cat['label']} Commands", "\n".join(lines), COLOR_PRIMARY)


class CategorySelect(discord.ui.Select):
    def __init__(self, is_admin: bool):
        self.is_admin = is_admin
        options = [
            discord.SelectOption(label=cat["label"], value=key, description=cat["desc"])
            for key, cat in visible_categories(is_admin).items()
        ]
        options.append(discord.SelectOption(label="🏠 Home", value="home", description="Back to the main menu"))
        super().__init__(placeholder="Select a category", options=options)

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        # re-check permission at click time in case roles changed
        is_admin = member_is_casino_admin(interaction.user) if interaction.guild else False
        if value == "admin" and not is_admin:
            await interaction.response.send_message("You don't have access to that category.", ephemeral=True)
            return
        embed = home_embed(is_admin) if value == "home" else category_embed(value)
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self, is_admin: bool):
        super().__init__(timeout=120)
        self.add_item(CategorySelect(is_admin))


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="help", description="Show all bot commands.")
    async def help(self, ctx: commands.Context):
        is_admin = member_is_casino_admin(ctx.author) if ctx.guild else False
        await ctx.send(embed=home_embed(is_admin), view=HelpView(is_admin))


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
