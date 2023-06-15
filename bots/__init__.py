from collections import OrderedDict

import discord

SUPPORT_SERVER_LINK = 'discord.gg/qRpYRTgvXM'
LOG_CHANNEL_ID = 1118867011448078417
DEVELOPER_ID = 572432137035317249


class DeleteButton(discord.ui.Button):
    def __init__(self, user: discord.User, label='Delete', style=discord.ButtonStyle.danger, *args, **kwargs):
        self.user_id = user.id
        super().__init__(label=label, style=style, *args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        if self.user_id == interaction.user.id:
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
