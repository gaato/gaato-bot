import re
from collections import OrderedDict

import discord
from discord.ext import commands

SUPPORT_SERVER_LINK = 'https://discord.gg/qRpYRTgvXM'


class OldDeleteButton(discord.ui.Button):

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


class LimitedSizeDict(OrderedDict):

    def __init__(self, size_limit=None, *args, **kwds):
        self.size_limit = size_limit
        super().__init__(*args, **kwds)
        self._check_size_limit()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._check_size_limit()

    def _check_size_limit(self):
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)
