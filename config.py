"""
Central place for the bot's visual identity — colors, emojis, embed helpers.
Change stuff here and the whole bot's look updates.
"""
import discord
from datetime import datetime

# ---- Brand ----
BOT_NAME = "NeonVault"
CURRENCY_NAME = "Shards"
CURRENCY_EMOJI = "🔷"
STARTING_BALANCE = 1000
DAILY_AMOUNT = 500
DAILY_COOLDOWN_HOURS = 24
MIN_CASHOUT_MULTIPLIER = 1.1  # can't cash out below this in crash/mines/balloon/hilo/etc.

# ---- Colors ----
COLOR_PRIMARY = 0x7C3AED   # violet
COLOR_WIN = 0x2ECC71       # green
COLOR_LOSE = 0xE74C3C      # red
COLOR_INFO = 0x3498DB      # blue
COLOR_GOLD = 0xF1C40F      # gold (jackpots)
COLOR_NEUTRAL = 0x2C2F33   # dark

# ---- Emojis (unicode, no custom emoji upload needed) ----
E_COIN = "🔷"
E_FIRE = "🔥"
E_SKULL = "💀"
E_GEM = "💎"
E_BOMB = "💣"
E_DICE = "🎲"
E_CARD = "🃏"
E_CROWN = "👑"
E_ROCKET = "🚀"
E_CHART_UP = "📈"
E_CHART_DOWN = "📉"
E_CHECK = "✅"
E_CROSS = "❌"
E_LOADING = "⏳"
E_TROPHY = "🏆"
E_SPARKLE = "✨"


def fmt(amount: int) -> str:
    """Format a currency amount consistently: 1,234 🔷"""
    return f"{amount:,} {CURRENCY_EMOJI}"


def base_embed(title: str, description: str = "", color: int = COLOR_PRIMARY) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color, timestamp=datetime.utcnow())
    e.set_footer(text=BOT_NAME)
    return e


def win_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(f"{E_FIRE} {title}", description, COLOR_WIN)


def lose_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(f"{E_SKULL} {title}", description, COLOR_LOSE)


def info_embed(title: str, description: str = "") -> discord.Embed:
    return base_embed(title, description, COLOR_INFO)


def error_embed(description: str) -> discord.Embed:
    return base_embed(f"{E_CROSS} Error", description, COLOR_LOSE)
