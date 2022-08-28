import os
import pathlib
import traceback

import discord
from discord.ext import commands

from .. import SUPPORT_SERVER_LINK, DeleteButton


BASE_DIR = pathlib.Path(__file__).parent.parent


class Bot(commands.Bot):
    def __init__(self, token, cogs, prefix):
        self.token = token
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=prefix, intents=intents)
        self.load_cogs(cogs)

    def load_cogs(self, cogs):
        for cog in cogs:
            self.load_extension(cog)
            print('Loaded ' + cog)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Pycord Version: {discord.__version__}')

    async def on_message(self, message):
        opt_out_users = []
        if os.path.exists(BASE_DIR / 'data' / 'opt-out-users.txt'):
            with open(BASE_DIR / 'data' / 'opt-out-users.txt', 'r') as f:
                for line in f.readlines():
                    if line.strip():
                        opt_out_users.append(int(line))
        if message.author.id in opt_out_users:
            return
        await super().on_message(message)

    async def on_message_edit(self, before, after):
        if before.content == after.content:
            return
        await self.on_message(after)

    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.CommandNotFound):
            return
        view = discord.ui.View(DeleteButton(self))
        embed = discord.Embed(
            title='Unhandled Error',
            color=0xff0000,
        )
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.reply(content=f'Please Report us!\n{SUPPORT_SERVER_LINK}', embed=embed, view=view)
        return await super().on_command_error(ctx, exception)

    def run(self):
        try:
            self.loop.run_until_complete(self.start(self.token))
        except discord.LoginFailure:
            print('Invalid Discord Token')
        except KeyboardInterrupt:
            print('Shutdown')
            self.loop.run_until_complete(self.close())
        except:
            traceback.print_exc()
