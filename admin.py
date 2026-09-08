import discord
from discord import app_commands
from discord.ext import commands

import database as db
from permissions import member_is_casino_admin
from config import fmt, win_embed, error_embed, info_embed, CURRENCY_NAME, STARTING_BALANCE


def is_casino_admin():
    async def predicate(ctx: commands.Context) -> bool:
        return member_is_casino_admin(ctx.author)
    return commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_command_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=error_embed("You need **Administrator** (or the `Casino Admin` role) to use this."))
        else:
            raise error

    @commands.hybrid_command(name="give", aliases=["g"], description=f"[Admin] Add {CURRENCY_NAME} to a user.")
    @app_commands.describe(member="Who to give points to", amount="How much to give")
    @is_casino_admin()
    async def give(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send(embed=error_embed("Amount must be positive."))
            return
        await db.add_balance(member.id, amount)
        new_bal = await db.get_balance(member.id)
        await ctx.send(embed=win_embed(
            "Points Granted",
            f"Gave **{fmt(amount)}** to {member.mention}\nNew balance: {fmt(new_bal)}"
        ))

    @commands.hybrid_command(name="remove", aliases=["rm"], description=f"[Admin] Remove {CURRENCY_NAME} from a user.")
    @app_commands.describe(member="Who to take points from", amount="How much to remove")
    @is_casino_admin()
    async def remove(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send(embed=error_embed("Amount must be positive."))
            return
        current = await db.get_balance(member.id)
        new_val = max(0, current - amount)
        await db.set_balance(member.id, new_val)
        await ctx.send(embed=info_embed(
            "Points Removed",
            f"Removed **{fmt(amount)}** from {member.mention}\nNew balance: {fmt(new_val)}"
        ))

    @commands.hybrid_command(name="setbalance", aliases=["sb"], description=f"[Admin] Set a user's {CURRENCY_NAME} to an exact amount.")
    @app_commands.describe(member="Who to edit", amount="Exact new balance")
    @is_casino_admin()
    async def setbalance(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount < 0:
            await ctx.send(embed=error_embed("Amount can't be negative."))
            return
        await db.set_balance(member.id, amount)
        await ctx.send(embed=info_embed("Balance Set", f"{member.mention}'s balance is now {fmt(amount)}"))

    @commands.hybrid_command(name="giveall", aliases=["tipall", "ta", "ga"], description=f"[Admin] Give {CURRENCY_NAME} to every member in the server.")
    @app_commands.describe(amount="How much each member receives")
    @is_casino_admin()
    async def giveall(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            await ctx.send(embed=error_embed("Amount must be positive."))
            return
        if ctx.interaction:
            await ctx.defer()
        status = await ctx.send(embed=info_embed("Airdropping...", "Fetching the full member list, this can take a moment on big servers."))

        count = 0
        async for m in ctx.guild.fetch_members(limit=None):
            if m.bot:
                continue
            await db.add_balance(m.id, amount)
            count += 1

        await status.edit(embed=win_embed(
            "Server-Wide Airdrop! 🎉",
            f"Everyone in the server just received **{fmt(amount)}**!\n"
            f"({count} members credited)"
        ))

    @commands.hybrid_command(name="removeall", aliases=["ra"], description=f"[Admin] Remove {CURRENCY_NAME} from every member in the server.")
    @app_commands.describe(amount="How much to remove from each member")
    @is_casino_admin()
    async def removeall(self, ctx: commands.Context, amount: int):
        if amount <= 0:
            await ctx.send(embed=error_embed("Amount must be positive."))
            return
        if ctx.interaction:
            await ctx.defer()
        status = await ctx.send(embed=info_embed("Removing points...", "Fetching the full member list, this can take a moment on big servers."))

        count = 0
        async for m in ctx.guild.fetch_members(limit=None):
            if m.bot:
                continue
            current = await db.get_balance(m.id)
            await db.set_balance(m.id, max(0, current - amount))
            count += 1

        await status.edit(embed=info_embed(
            "Server-Wide Deduction",
            f"Removed **{fmt(amount)}** from everyone in the server.\n"
            f"({count} members affected)"
        ))

    @commands.hybrid_command(name="resetbalance", aliases=["rb"], description=f"[Admin] Reset a user back to the starting balance.")
    @app_commands.describe(member="Who to reset")
    @is_casino_admin()
    async def resetbalance(self, ctx: commands.Context, member: discord.Member):
        await db.set_balance(member.id, STARTING_BALANCE)
        await ctx.send(embed=info_embed("Balance Reset", f"{member.mention} is back to {fmt(STARTING_BALANCE)}"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
