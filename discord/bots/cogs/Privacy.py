import os
import pathlib

import discord
from discord.commands import slash_command
from discord.ext import commands


BASE_DIR = pathlib.Path(__file__).parent.parent


class Privacy(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @slash_command(name='privacy-policy')
    async def privacy_policy(self, ctx: discord.ApplicationContext):
        """Show the privacy policy"""
        with open(BASE_DIR / 'config' / 'privacy-policy.md', 'r') as f:
            await ctx.respond(f.read())

    @slash_command(name='opt-out')
    async def opt_out(self, ctx: discord.ApplicationContext):
        """Opt out of your message content data to be tracked"""
        opt_out_users = []
        if os.path.exists(BASE_DIR / 'data' / 'opt-out-users.txt'):
            with open(BASE_DIR / 'data' / 'opt-out-users.txt', 'r') as f:
                for line in f.readlines():
                    if line.strip():
                        opt_out_users.append(int(line))
        if ctx.author.id in opt_out_users:
            await ctx.respond('Your message content is already off-track. To use other commands, please use the /opt-in command.')
        else:
            opt_out_users.append(ctx.author.id)
            with open(BASE_DIR / 'data' / 'opt-out-users.txt', 'w') as f:
                for user in opt_out_users:
                    f.write(str(user) + '\n')
            await ctx.respond('This bot will not track your message content from now on. Most commands will no longer respond.')

    @slash_command(name='opt-in')
    async def opt_in(self, ctx: discord.ApplicationContext):
        """Opt out of your message content data to be tracked"""
        opt_out_users = []
        if os.path.exists(BASE_DIR / 'data' / 'opt-out-users.txt'):
            with open(BASE_DIR / 'data' / 'opt-out-users.txt', 'r') as f:
                for line in f.readlines():
                    if line.strip():
                        opt_out_users.append(int(line))
        if ctx.author.id in opt_out_users:
            opt_out_users.remove(ctx.author.id)
            with open(BASE_DIR / 'data' / 'opt-out-users.txt', 'w') as f:
                for user in opt_out_users:
                    f.write(str(user) + '\n')
            await ctx.respond('This bot will now track the content of your messages. It will only be used to provide commands. Use the /privacy-policy command to view the privacy policy.')
        else:
            await ctx.respond('This bot is already tracking your message content.')


def setup(bot):
    return bot.add_cog(Privacy(bot))
