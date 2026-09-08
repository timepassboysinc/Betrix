import discord


def member_is_casino_admin(member: discord.Member) -> bool:
    """Administrator permission, or a role literally named 'Casino Admin'."""
    if member.guild_permissions.administrator:
        return True
    return any(r.name.lower() == "casino admin" for r in member.roles)
