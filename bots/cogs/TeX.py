import base64
import io
from typing import Optional

import aiohttp
import discord
from discord.ext import commands

from .. import SUPPORT_SERVER_LINK, DeleteButton


class LimitedSizeDict(dict):

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


class TeX(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_message_id_to_bot_message = LimitedSizeDict(size_limit=100)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.content != after.content:
            if before.id in self.user_message_id_to_bot_message:
                await self.user_message_id_to_bot_message[before.id].delete()

    async def respond(self, ctx: commands.Context, code: str, file_type: str, plain: Optional[bool], spoiler: bool):

        async with ctx.channel.typing():

            view = discord.ui.View(DeleteButton(self.bot))

            code = code.replace('```tex', '').replace('```', '').strip()

            url = 'http://127.0.0.1:9000/api'
            params = {
                'type': file_type,
                'plain': plain,
                'code': code,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=params) as r:
                    if r.status == 200:
                        result = await r.json()
                    else:
                        embed = discord.Embed(
                            title='Connection Error',
                            description=f'{r.status}',
                            color=0xff0000,
                        )
                        embed.set_author(
                            name=ctx.author.name,
                            icon_url=ctx.author.display_avatar.url,
                        )
                        return await ctx.reply(content=f'Please Report us!\n{SUPPORT_SERVER_LINK}', embed=embed, view=view)

            match result['status']:
                case 0:
                    embed = discord.Embed(color=0x008000)
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar.url,
                    )
                    if file_type == 'png':
                        embed.set_image(url='attachment://tex.png')
                    return await ctx.reply(
                        file=discord.File(
                            io.BytesIO(base64.b64decode(result['result'])),
                            filename='tex.pdf' if file_type == 'pdf' else 'tex.png',
                            spoiler=spoiler,
                        ),
                        embed=embed,
                        view=view,
                    )
                case 1:
                    embed = discord.Embed(
                        title='Rendering Error',
                        description=f'```\n{result["error"]}\n```',
                        color=0xff0000,
                    )
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar.url,
                    )
                    return await ctx.reply(embed=embed, view=view)
                case 2:
                    embed = discord.Embed(
                        title='Timed Out',
                        color=0xff0000,
                    )
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar,
                    )
                    return await ctx.reply(embed=embed, view=view)
                case _:
                    embed = discord.Embed(
                        title='Unhandled Error',
                        color=0xff0000,
                    )
                    embed.set_author(
                        name=ctx.author.name,
                        icon_url=ctx.author.display_avatar.url,
                    )
                    return await ctx.reply(content=f'Please report us!\n{SUPPORT_SERVER_LINK}', embed=embed, view=view)

    @commands.command()
    async def tex(self, ctx: commands.Context, *, code: str):
        """TeX to image (in math mode)"""
        m = await self.respond(ctx, code, 'png', False, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def texp(self, ctx: commands.Context, *, code: str):
        """TeX to image (out of math mode)"""
        m = await self.respond(ctx, code, 'png', True, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def stex(self, ctx: commands.Context, *, code: str):
        """TeX to spoiler image (in math mode)"""
        m = await self.respond(ctx, code, 'png', False, True)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def stexp(self, ctx: commands.Context, *, code: str):
        """TeX to spoiler image (out of math mode)"""
        m = await self.respond(ctx, code, 'png', True, True)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def texpdf(self, ctx: commands.Context, *, code: str):
        """TeX to PDF (from preamble)"""
        m = await self.respond(ctx, code, 'pdf', None, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m


def setup(bot):
    return bot.add_cog(TeX(bot))
