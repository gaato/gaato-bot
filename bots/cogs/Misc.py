import sqlite3
import pathlib

import discord
from discord.ext import commands
from sudachipy import tokenizer, dictionary

from .. import DeleteButton


BASE_DIR = pathlib.Path(__file__).parent.parent
dbname = BASE_DIR.parent / 'db.sqlite3'
conn = sqlite3.connect(dbname, check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS pin (channel_id INTEGER, message_id INTEGER)')
c.execute('SELECT * FROM pin')
pins = dict(c.fetchall())


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tokenizer_obj = dictionary.Dictionary().create()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.channel.id not in pins:
            return
        last_message = discord.utils.find(
            lambda m: len(m.embeds) > 0 and m.embeds[0].footer.text.startswith('Pinned in'),
            await message.channel.history(limit=10).flatten(),
        )
        if last_message is not None:
            await last_message.delete()
        pinned_message = await message.channel.fetch_message(pins[message.channel.id])
        if pinned_message is None:
            return
        embed = discord.Embed()
        embed.set_author(
            name=pinned_message.author.display_name,
            icon_url=pinned_message.author.display_avatar.url,
        )
        embed.description = pinned_message.content
        embed.set_footer(
            text=f'Pinned in #{message.channel.name}',
        )
        await message.channel.send(embed=embed)

    @discord.slash_command(
        name='sudachi',
        description='形態素解析',
    )
    async def sudachi(self, ctx: discord.ApplicationContext, text: str):
        """形態素解析"""
        mode = tokenizer.Tokenizer.SplitMode.C
        tokens = self.tokenizer_obj.tokenize(text, mode)
        outputs = [f'{text}']
        for t in tokens:
            outputs.append(f'{t.surface()}\t{",".join(t.part_of_speech())}\t{t.reading_form()}\t{t.normalized_form()}')
        view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
        await ctx.respond(f'```\n' + '\n'.join(outputs) + '\n```', view=view)

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
    return bot.add_cog(Misc(bot))
