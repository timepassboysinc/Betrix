import asyncio
import os
import logging
import time

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import init_db
from config import BOT_NAME

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX", ".")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log", encoding="utf-8")],
)
log = logging.getLogger("bot")

ON_HOSTED_PLATFORM = "REPL_ID" in os.environ or os.environ.get("RENDER") == "true"
if ON_HOSTED_PLATFORM:
    from keep_alive import keep_alive
    keep_alive()
    log.info("Detected a hosted platform (Replit/Render) — keep-alive web server started.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # needed for giveall/removeall/rain to see every member

INITIAL_EXTENSIONS = [
    "cogs.economy",
    "cogs.admin",
    "cogs.help",
    "cogs.feedback",
    "cogs.games.coinflip",
    "cogs.games.dice",
    "cogs.games.slots",
    "cogs.games.blackjack",
    "cogs.games.crash",
    "cogs.games.limbo",
    "cogs.games.mines",
    "cogs.games.roulette",
    "cogs.games.plinko",
    "cogs.games.keno",
    "cogs.games.poker",
    "cogs.games.pvp",
    "cogs.games.baccarat",
    "cogs.games.hilo",
    "cogs.games.horse",
    "cogs.games.casebattle",
    "cogs.games.balloon",
    "cogs.games.rat",
    "cogs.games.classicslots",
    "cogs.games.crazydice",
    "cogs.games.diamonds",
    "cogs.games.dicewar",
    "cogs.games.gtn",
    "cogs.games.jackpotwheel",
    "cogs.games.match",
    "cogs.games.slide",
    "cogs.games.tight",
    "cogs.games.tournament",
    "cogs.games.blackjackdice",
    "cogs.games.progressivecoinflip",
    "cogs.games.cards",
    "cogs.games.rain",
]


def build_bot() -> commands.Bot:
    bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
    bot._synced = False

    @bot.event
    async def on_ready():
        log.info(f"Logged in as {bot.user} ({bot.user.id})")
        await bot.change_presence(activity=discord.Game(name=f"{PREFIX}help | {BOT_NAME}"))
        if not bot._synced:
            try:
                synced = await bot.tree.sync()
                log.info(f"Synced {len(synced)} slash commands.")
                bot._synced = True
            except Exception:
                log.exception("Failed to sync slash commands.")

    @bot.event
    async def on_disconnect():
        log.warning("Disconnected from Discord — discord.py will attempt to reconnect automatically.")

    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return
        log.exception(f"Command error in '{ctx.command}': {error}")
        try:
            await ctx.send(f"⚠️ Something went wrong running that command: `{error}`")
        except discord.HTTPException:
            pass

    @bot.tree.error
    async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        log.exception(f"App command error in '{interaction.command}': {error}")
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"⚠️ Something went wrong: `{error}`", ephemeral=True)
            else:
                await interaction.response.send_message(f"⚠️ Something went wrong: `{error}`", ephemeral=True)
        except discord.HTTPException:
            pass

    return bot


async def run_once():
    """One full connection lifecycle. discord.py already auto-reconnects on
    ordinary network drops; this only returns when the connection is well
    and truly dead (or an unhandled error occurs), so run_forever() below
    can restart it from scratch."""
    await init_db()
    bot = build_bot()
    async with bot:
        for ext in INITIAL_EXTENSIONS:
            try:
                await bot.load_extension(ext)
                log.info(f"Loaded {ext}")
            except Exception as e:
                log.exception(f"Failed to load {ext}: {e}")
        await bot.start(TOKEN)


def run_forever():
    """Keeps the bot alive across crashes with exponential backoff, so a
    single unhandled exception in a game doesn't take the whole process
    down for good. This is separate from hosting the process itself
    24/7 — see the README for that part."""
    backoff = 5
    while True:
        try:
            asyncio.run(run_once())
        except KeyboardInterrupt:
            log.info("Shutting down (Ctrl+C).")
            return
        except discord.LoginFailure:
            log.error("Login failed — check DISCORD_TOKEN in your .env file.")
            return
        except Exception:
            log.exception(f"Bot crashed. Restarting in {backoff}s...")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        else:
            return


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("Set DISCORD_TOKEN in your .env file first.")
    run_forever()
