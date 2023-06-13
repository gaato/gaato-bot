import os
import pathlib
from collections import OrderedDict

import aiohttp
import discord
import dotenv
from discord.ext import commands, pages

from .. import SUPPORT_SERVER_LINK, DeleteButton

dotenv.load_dotenv(verbose=True)
URL = 'http://api.wolframalpha.com/v2/query'
BASE_DIR = pathlib.Path(__file__).parent.parent


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


class Wolfram(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_message_id_to_bot_message = LimitedSizeDict(size_limit=100)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content:
            if before.id in self.user_message_id_to_bot_message:
                await self.user_message_id_to_bot_message[before.id].delete()

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.id in self.user_message_id_to_bot_message:
            await self.user_message_id_to_bot_message[message.id].delete()


    @commands.command(aliases=['wolfram'])
    async def wolf(self, ctx: commands.Context, *, query: str):

        async with ctx.channel.typing():
            view = discord.ui.View(DeleteButton(ctx.author), timeout=None)

            async with aiohttp.ClientSession() as session:
                async with session.get(URL, params={'input': query, 'format': 'image,plaintext', 'output': 'JSON', 'appid': os.environ.get('WOLFRAM_APPID')}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                    else:
                        embed = discord.Embed(
                            title='Connection Error',
                            description=f'{resp.status}',
                            color=0xff0000
                        )
                        embed.set_author(
                            name=ctx.author.name,
                            icon_url=ctx.author.display_avatar.url
                        )
                        self.user_message_id_to_bot_message[ctx.message.id] = await ctx.reply(content=f'Please Report us!\n{SUPPORT_SERVER_LINK}', embed=embed, view=view)
                        return

            page_list = []
            if data['queryresult']['success']:
                for pod in data['queryresult']['pods']:
                    for subpod in pod['subpods']:
                        embed = discord.Embed(
                            title=pod['title'],
                            description=subpod['plaintext'],
                            color=0x00ff00,
                        )
                        if 'img' in subpod:
                            embed.set_image(url=subpod['img']['src'])
                            embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
                        page_list.append(embed)
                paginator = pages.Paginator(pages=page_list)
                # paginator.add_button(DeleteButton(self.bot))
                m = await paginator.send(ctx)
            else:
                embed = discord.Embed(
                    title='Error',
                    description='Wolfram|Alpha は、その入力を理解できませんでした。',
                    color=0xff0000,
                )
                embed.set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar.url
                )
                m = await ctx.reply(embed=embed, view=view)
            self.user_message_id_to_bot_message[ctx.message.id] = m

def setup(bot):
    return bot.add_cog(Wolfram(bot))
