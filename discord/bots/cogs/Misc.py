import os
import pathlib

from discord.ext import commands
from openai import AsyncOpenAI

import discord

from .. import DeleteButton

# from sudachipy import tokenizer, dictionary



BASE_DIR = pathlib.Path(__file__).parent.parent

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # self.tokenizer_obj = dictionary.Dictionary().create()

    async def fetch_message_history(self, channel: discord.TextChannel, limit: int = 5):
        history = await channel.history(limit=limit).flatten()
        messages = []
        for message in history:
            messages.append({
                "role": "user" if message.author != self.bot.user else "assistant",
                "content": f"Author:\n{message.author.mention}\nContent:\n{message.content}"
            })
        messages.reverse()
        return messages

    @commands.Cog.listener("on_message")
    async def on_mentioned(self, message: discord.Message):
        if message.author.bot:
            return
        if self.bot.user.mentioned_in(message):
            async with message.channel.typing():
                history = await self.fetch_message_history(message.channel, limit=5)
                history.append({
                    "role": "user",
                    "content": message.content
                })
                response = await client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "あなたはあるDiscordサーバーのメンバーです。以下は直近のメッセージ履歴です。そのサーバーのメンバーらしくカジュアルに返信してください。",
                        },
                        *history
                    ],
                )
                allowed_mentions = discord.AllowedMentions.none()
                allowed_mentions.replied_user = True
                await message.reply(response.choices[0].message.content, allowed_mentions=allowed_mentions)
                await self.bot.process_commands(message)

    # @discord.slash_command(
    #     name='sudachi',
    #     description='形態素解析',
    # )
    # async def sudachi(self, ctx: discord.ApplicationContext, text: str):
    #     """形態素解析"""
    #     mode = tokenizer.Tokenizer.SplitMode.C
    #     tokens = self.tokenizer_obj.tokenize(text, mode)
    #     outputs = [f'{text}']
    #     for t in tokens:
    #         outputs.append(f'{t.surface()}\t{",".join(t.part_of_speech())}\t{t.reading_form()}\t{t.normalized_form()}')
    #     view = discord.ui.View(DeleteButton(ctx.author), timeout=None)
    #     await ctx.respond(f'```\n' + '\n'.join(outputs) + '\n```', view=view)


def setup(bot: commands.Bot):
    return bot.add_cog(Misc(bot))