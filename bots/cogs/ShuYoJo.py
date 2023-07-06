import sqlite3
import pathlib
import re
import urllib.parse

import discord
from discord.ext import commands


BASE_DIR = pathlib.Path(__file__).parent.parent
dbname = BASE_DIR.parent / 'db.sqlite3'
conn = sqlite3.connect(dbname, check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS pin (channel_id INTEGER, message_id INTEGER)')
c.execute('SELECT * FROM pin')
pins = dict(c.fetchall())

class ShuYoJo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id not in pins:
            return
        last_message = discord.utils.find(
            lambda m: len(m.embeds) > 0 and m.embeds[0].footer.text and m.embeds[0].footer.text.startswith('Pinned'),
            await message.channel.history(limit=10).flatten(),
        )
        if last_message is not None:
            await last_message.delete()
        pinned_message = await message.channel.fetch_message(pins[message.channel.id])
        if pinned_message is None:
            return
        embed = discord.Embed(description=pinned_message.content)
        embed.set_footer(
            text=f'Pinned by {pinned_message.author.display_name}',
            icon_url=pinned_message.author.display_avatar.url,
        )
        if m := re.search('```(.*?)```', pinned_message.content, re.DOTALL):
            copyable_text = m.group(1).strip()
            view = discord.ui.View(discord.ui.Button(
                label='クリップボードにコピー',
                style=discord.ButtonStyle.primary,
                emoji='📋',
                url=f'https://pythonbot.fly.dev/u/600922778509770754?text={urllib.parse.quote(copyable_text)}',
            ))
        else:
            view = None
        await message.channel.send(embed=embed, view=view)

    @discord.message_command(
        name='pin',
        description='チャンネルの一番下にメッセージをピン留め',
        default_member_permissions=discord.Permissions(manage_messages=True),
    )
    async def pin(self, ctx: discord.ApplicationContext, message: discord.Message):
        """チャンネルの一番下にメッセージをピン留め"""
        if ctx.channel.id in pins:
            c.execute('UPDATE pin SET message_id = ? WHERE channel_id = ?', (message.id, ctx.channel.id))
        else:
            c.execute('INSERT INTO pin VALUES (?, ?)', (ctx.channel.id, message.id))
        pins[ctx.channel.id] = message.id
        conn.commit()
        await ctx.respond('ピン留めしました', ephemeral=True)

    @discord.slash_command(
        name='unpin',
        description='ピン留めを解除',
        default_member_permissions=discord.Permissions(manage_messages=True),
    )
    async def unpin(self, ctx: discord.ApplicationContext):
        """ピン留めを解除"""
        c.execute('DELETE FROM pin WHERE channel_id = ?', (ctx.channel.id,))
        del pins[ctx.channel.id]
        conn.commit()
        await ctx.respond('ピン留めを解除しました', ephemeral=True)


def setup(bot):
    return bot.add_cog(ShuYoJo(bot))
