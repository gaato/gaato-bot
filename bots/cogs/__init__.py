import re

import discord
from discord.ext import commands


class DeleteButton(discord.ui.Button):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        super().__init__(label='Delete')

    async def callback(self, interaction: discord.Interaction):
        user_id = None
        for embed in interaction.message.embeds:
            if embed.author.icon_url and (m := re.match(r'https://cdn.discordapp.com/avatars/(\d+)/(.+)', embed.author.icon_url)):
                user_id = int(m.group(1))
                break
        if user_id is not None and interaction.user.id == user_id:
            await interaction.message.delete()
