import base64
import io
import pathlib
import sqlite3
from typing import Optional, Tuple

import aiohttp
import discord
from discord.ext import commands

from .. import SUPPORT_SERVER_LINK, LimitedSizeDict, DeleteButton

BASE_DIR = pathlib.Path(__file__).parent.parent
dbname = BASE_DIR.parent / 'db.sqlite3'
conn = sqlite3.connect(dbname, check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS tex (message_id INTEGER, author_id INTEGER, code TEXT, plain INTEGER, spoiler INTEGER)')


async def respond_core(
    author: discord.User,
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
                    name=author.name,
                    icon_url=author.display_avatar.url,
                )
                return '', embed, None
    match result['status']:
        case 0:
            embed = discord.Embed(color=0x008000)
            embed.set_author(
                name=author.name,
                icon_url=author.display_avatar.url,
            )
            if file_type == 'png':
                embed.set_image(url='attachment://tex.png')
            file = discord.File(
                io.BytesIO(base64.b64decode(result['result'])),
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
                name=author.name,
                icon_url=author.display_avatar.url,
            )
            return '', embed, None
        case 2:
            embed = discord.Embed(
                title='Timed Out',
                color=0xff0000,
            )
            embed.set_author(
                name=author.name,
                icon_url=author.display_avatar,
            )
            return '', embed, None
        case _:
            embed = discord.Embed(
                title='Unhandled Error',
                color=0xff0000,
            )
            embed.set_author(
                name=author.name,
                icon_url=author.display_avatar.url,
            )
            return f'Please report us!\n{SUPPORT_SERVER_LINK}', embed, None


class EditButton(discord.ui.Button):
    def __init__(self, label='Edit', style=discord.ButtonStyle.primary, **kwargs):
        super().__init__(label=label, style=style, **kwargs)

    async def edit_callback(self, interaction: discord.Interaction):
        c = conn.cursor()
        c.execute('SELECT * FROM tex WHERE message_id = ?', (interaction.message.id,))
        result = c.fetchone()
        if result is None:
            embed = discord.Embed(
                title='Error',
                description='Not found.',
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.send_modal(TeXModal(bool(result[3]), bool(result[4]), result[2]))


class TeXModal(discord.ui.Modal):
    def __init__(self, plain, spoiler, value='', title='LaTeX to Image', *arg, **kwargs):
        self.plain = plain
        self.spoiler = spoiler
        super().__init__(title=title, *arg, **kwargs)
        self.add_item(discord.ui.InputText(
            label = 'Text' if plain else 'Code',
            placeholder='Input TeX code here',
            style=discord.InputTextStyle.long if plain else discord.InputTextStyle.short,
            value=value,
        ))

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(invisible=False)
        content, embed, file = await respond_core(
            interaction.user,
            self.children[0].value,
            'png',
            self.plain,
            self.spoiler,
        )
        view = discord.ui.View(DeleteButton(interaction.user), EditButton())
        if file is None:
            m = await interaction.followup.send(content=content, embed=embed, view=view, wait=True)
        else:
            m = await interaction.followup.send(content=content, embed=embed, file=file, view=view, wait=True)
        c = conn.cursor()
        c.execute('INSERT INTO tex VALUES (?, ?, ?, ?, ?)', (m.id, interaction.user.id, self.children[0].value, int(self.plain), int(self.spoiler)))


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
            view = discord.ui.View(DeleteButton(ctx.author))
            code = code.replace('```tex', '').replace('```', '').strip()
            content, embed, file = await respond_core(ctx.author, code, file_type, plain, spoiler)
            if file is None:
                m = await ctx.send(content=content, embed=embed, view=view)
            else:
                m = await ctx.send(content=content, embed=embed, file=file, view=view)
            return m

    @commands.command()
    async def tex(self, ctx: commands.Context, *, code: str):
        """LaTeX to image (in math mode)"""
        m = await self.respond(ctx, code, 'png', False, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def texp(self, ctx: commands.Context, *, code: str):
        """LaTeX to image (out of math mode)"""
        m = await self.respond(ctx, code, 'png', True, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def stex(self, ctx: commands.Context, *, code: str):
        """LaTeX to spoiler image (in math mode)"""
        m = await self.respond(ctx, code, 'png', False, True)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def stexp(self, ctx: commands.Context, *, code: str):
        """LaTeX to spoiler image (out of math mode)"""
        m = await self.respond(ctx, code, 'png', True, True)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @commands.command()
    async def texpdf(self, ctx: commands.Context, *, code: str):
        """LaTeX to PDF (from preamble)"""
        m = await self.respond(ctx, code, 'pdf', None, False)
        self.user_message_id_to_bot_message[ctx.message.id] = m

    @discord.slash_command(
        name='tex',
        description='TeX to image',
    )
    async def tex_slash(self, ctx: discord.ApplicationContext, plain: bool = False, spoiler: bool = False):
        modal = TeXModal(plain, spoiler)
        await ctx.send_modal(modal)


def setup(bot):
    return bot.add_cog(TeX(bot))
