import copy
import io
import os
import pathlib
import pprint
import traceback
from typing import Union

import discord
from discord.ext import commands

from .. import DEVELOPER_ID, LOG_CHANNEL_ID, SUPPORT_SERVER_LINK, DeleteButton

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
        self.logging_channel = self.get_channel(LOG_CHANNEL_ID)
        self.developer = self.get_user(DEVELOPER_ID)


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
        if isinstance(exception, commands.UserInputError):
            view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
            embed = discord.Embed(
                title='Invalid Input',
                description=f'```\n{exception}\n```',
                color=0xff0000,
            )
            embed.set_author(
                name=ctx.author.name,
                icon_url=ctx.author.display_avatar.url,
            )
            await ctx.reply(embed=embed, view=view)
            return
        view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
        embed = discord.Embed(
            title='Unhandled Error',
            color=0xff0000,
        )
        embed.set_author(
            name=ctx.author.name,
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.reply(content=f'Please Report us!\n{SUPPORT_SERVER_LINK}', embed=embed, view=view)
        await self.log_error(ctx, exception)
        return await super().on_command_error(ctx, exception)

    async def on_slash_command_error(self, ctx: discord.ApplicationContext, exception: Exception):
        await self.log_error(ctx, exception)
        return await super().on_slash_command_error(ctx, exception)

    async def log_error(self, ctx: Union[commands.Context, discord.ApplicationContext], exception: Exception):
        if isinstance(ctx, commands.Context):
            content = ctx.message.content
        else:
            content = f'/{ctx.name} {" ".join([str(arg) for arg in ctx.options.values()])}'
        exception_text = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        await self.logging_channel.send(content=f'```\n{content}\n```', file=discord.File(io.StringIO(exception_text), filename='error.txt'))

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
