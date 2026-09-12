import discord
from discord.ext import commands

from config import base_embed, COLOR_PRIMARY, BOT_NAME

FEEDBACK_CHANNEL_ID = 1547258558742011985


class FeedbackModal(discord.ui.Modal, title="Send Feedback"):
    feedback = discord.ui.TextInput(
        label="Your suggestion or feedback",
        style=discord.TextStyle.paragraph,
        placeholder="Tell us what you think, report a bug, or suggest a feature...",
        max_length=1000,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(FEEDBACK_CHANNEL_ID)
        if channel is None:
            try:
                channel = await interaction.client.fetch_channel(FEEDBACK_CHANNEL_ID)
            except discord.HTTPException:
                channel = None

        if channel is None:
            await interaction.response.send_message(
                "Thanks — but I couldn't find the feedback channel to deliver this to. "
                "Let a server admin know so they can check the bot's config.",
                ephemeral=True,
            )
            return

        embed = base_embed(f"📩 New Feedback — {BOT_NAME}", str(self.feedback), COLOR_PRIMARY)
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id} • From: {interaction.guild.name if interaction.guild else 'DM'}")

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            await interaction.response.send_message(
                "Thanks — but I wasn't able to deliver that to the feedback channel. "
                "A server admin may need to check my permissions there.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message("Thanks for your feedback! 🙏", ephemeral=True)


class FeedbackPromptView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Give Feedback", emoji="📝", style=discord.ButtonStyle.primary)
    async def give_feedback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FeedbackModal())


class Feedback(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if self.bot.user is None or self.bot.user not in message.mentions:
            return
        if message.mention_everyone:
            return
        await message.reply(
            "Got a suggestion or some feedback for me? Tap the button below!",
            view=FeedbackPromptView(),
            mention_author=False,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Feedback(bot))
