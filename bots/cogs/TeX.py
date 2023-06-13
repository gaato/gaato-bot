import base64
import io
from collections import OrderedDict
from typing import Optional, Union, Tuple

import aiohttp
import discord
from discord.ext import commands

from .. import SUPPORT_SERVER_LINK, DeleteButton, LimitedSizeDict


async def respond_core(
        ctx: Union[discord.ApplicationContext, commands.Context],
        code: str, file_type: str,
        plain: Optional[bool],
        spoiler: bool
    ) -> Tuple[str, discord.Embed, Optional[discord.File]]:
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
                    return '', embed, None
        match result['status']:
            case 0:
                embed = discord.Embed(color=0x008000)
                embed.set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar.url,
                )
                if file_type == 'png':
                    embed.set_image(url='attachment://tex.png')
                file = discord.File(
                    io.BytesIO(base64.b64decode(result['data'])),
                    filename='tex.png',
                    spoiler=spoiler,
                )
                return '', embed, file
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
                return '', embed, None
            case 2:
                embed = discord.Embed(
                    title='Timed Out',
                    color=0xff0000,
                )
                embed.set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar,
                )
                return '', embed, None
            case _:
                embed = discord.Embed(
                    title='Unhandled Error',
                    color=0xff0000,
                )
                embed.set_author(
                    name=ctx.author.name,
                    icon_url=ctx.author.display_avatar.url,
                )
                return f'Please report us!\n{SUPPORT_SERVER_LINK}', embed, None


class TeXModal(discord.ui.Modal):
    def __init__(self, ctx: discord.ApplicationContext, plain, spoiler, *arg, **kwargs):
        self.ctx = ctx
        self.plain = plain
        self.spoiler = spoiler
        super().__init__(*arg, **kwargs)
        self.add_item(discord.ui.InputText(
            label = 'Text' if plain else 'Code',
            placeholder='Input TeX code here',
            multiline=True,
        ))

    async def callback(self, interaction: discord.Interaction):
        content, embed, file = await respond_core(
            self.ctx,
            self.children[0].value,
            'png',
            self.plain,
            self.spoiler,
        )
        await interaction.respond(content=content, embed=embed, file=file)

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
            content, embed, file = await respond_core(ctx, code, file_type, plain, spoiler)
            m = await ctx.send(content=content, embed=embed, file=file, view=view)
            return m

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

    @discord.slash_command(
        name='tex',
        description='TeX to image',
    )
    async def tex_slash(self, ctx: commands.Context, plain: bool = False, spoiler: bool = False):
        await TeXModal(ctx, plain, spoiler).start()


def setup(bot):
    return bot.add_cog(TeX(bot))
