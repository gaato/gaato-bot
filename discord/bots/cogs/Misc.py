import os
import pathlib
from collections import defaultdict
from datetime import datetime, timedelta

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
        self.mention_times = defaultdict(list)
        # self.tokenizer_obj = dictionary.Dictionary().create()

    async def fetch_message_history(self, channel: discord.TextChannel, limit: int = 10):
        history = await channel.history(limit=limit).flatten()
        messages = []
        for message in history:
            messages.append({
                "role": "user" if message.author != self.bot.user else "assistant",
                "content": f"Author: {message.author.mention}\n\nContent:\n{message.content}"
            })
        messages.reverse()
        return messages

    def is_mention_limit_exceeded(self, user_id: int, time_limit: int = 60, max_mentions: int = 3):
        now = datetime.now()
        mention_times = self.mention_times[user_id]
        # Remove mentions older than time_limit seconds
        self.mention_times[user_id] = [time for time in mention_times if now - time < timedelta(seconds=time_limit)]
        # Check if mention limit is exceeded
        print(self.mention_times)
        return len(self.mention_times[user_id]) >= max_mentions

    @commands.Cog.listener("on_message")
    async def on_mentioned(self, message: discord.Message):
        if message.author.bot:
            return
        if str(self.bot.user.id) in message.content:
            if self.is_mention_limit_exceeded(message.author.id):
                return
            self.mention_times[message.author.id].append(datetime.now())
            async with message.channel.typing():
                history = await self.fetch_message_history(message.channel, limit=10)
                history.append({
                    "role": "assistant" if message.author.id == self.bot.user.id else "user",
                    "content": message.content,
                })
                if message.author.id == 572432137035317249:  # gaato.
                    response = await client.chat.completions.create(
                        model=   "gpt-4-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": f"あなたはあるDiscordサーバーのメンバーである{self.bot.user.mention}です。"
                                "以下の様々なユーザーによる直近のメッセージ履歴を参考に、"
                                "あなたがメンションされている最後のメッセージに返信してください。"
                            },
                            *history
                        ],
                    )
                else:
                    response = await client.chat.completions.create(
                        model=   "gpt-3.5-turbo",
                        messages=[
                            {
                                "role": "system",
                                "content": f"あなたはあるDiscordサーバーのメンバーである{self.bot.user.mention}です。"
                                "以下は直近のメッセージ履歴です。"
                                "一言で返信してください。"
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