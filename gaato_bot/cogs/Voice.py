import asyncio
from typing import Dict
import random

import discord
from gaato_bot.core.bot import GaatoBot
from discord.ext import commands
import youtube_dl


# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

client = discord.Client()

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class AudioQueue(asyncio.Queue):
    def __init__(self):
        super().__init__(100)

    def __getitem__(self, idx):
        return self._queue[idx]

    def to_list(self):
        return list(self._queue)

    def reset(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, idx):
        del self._queue[idx]


class AudioStatus:
    def __init__(self, ctx: commands.Context, vc: discord.VoiceClient):
        self.vc: discord.VoiceClient = vc
        self.ctx: commands.Context = ctx
        self.queue = AudioQueue()
        self.playing = asyncio.Event()
        self.loop = False
        self.loopqueue = False
        asyncio.create_task(self.playing_task())

    async def add_audio(self, player, url):
        await self.queue.put((player, url))

    def get_list(self):
        return self.queue.to_list()

    async def playing_task(self):
        while True:
            try:
                player, url = await asyncio.wait_for(self.queue.get(), timeout=180)
            except asyncio.TimeoutError:
                asyncio.create_task(self.leave())
            while True:
                self.playing.clear()
                self.vc.play(player, after=self.play_next)
                await self.ctx.send(f'{player.title}を再生します...')
                await self.playing.wait()
                if self.loop:
                    player = await YTDLSource.from_url(url, loop=client.loop)
                elif self.loopqueue:
                    last_player = await YTDLSource.from_url(url, loop=client.loop)
                    await self.add_audio(last_player, url)
                    break
                else:
                    break

    def play_next(self, err=None):
        self.playing.set()

    async def leave(self):
        self.queue.reset()
        if self.vc:
            await self.vc.disconnect()
            self.vc = None

    @property
    def is_playing(self):
        return self.vc.is_playing()

    def skip(self):
        self.vc.stop()
        self.play_next()


class Voice(commands.Cog):
    def __init__(self, bot: GaatoBot):
        self.bot = bot
        self.audio_statuses: Dict[int, AudioStatus] = {}

    @commands.command()
    async def join(self, ctx: commands.Context):
        # VoiceChannel未参加
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send('先にボイスチャンネルに参加してください')
        vc = await ctx.author.voice.channel.connect()
        self.audio_statuses[ctx.guild.id] = AudioStatus(ctx, vc)

    @commands.command()
    async def play(self, ctx: commands.Context, *, url: str):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            await ctx.invoke(self.join)
            status = self.audio_statuses[ctx.guild.id]
        player = await YTDLSource.from_url(url, loop=client.loop)
        await status.add_audio(player, url)
        await ctx.send(f'{player.title}を再生リストに追加しました')

    @commands.command()
    async def skip(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if not status.is_playing:
            return await ctx.send('既に停止しています')
        await status.skip()
        await ctx.send('スキップしました')

    @commands.command()
    async def disconnect(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('ボイスチャンネルにまだ未参加です')
        await status.leave()
        del self.audio_statuses[ctx.guild.id]

    @commands.command()
    async def queue(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('先にボイスチャンネルに参加してください')
        queue = status.get_list()
        songs = ""
        for i, (player, _) in enumerate(queue):
            songs += f"{i + 1}. {player.title}\n"
        await ctx.send(songs)

    @commands.command()
    async def shuffle(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        status.queue.shuffle()
        return await ctx.send('シャッフルしました')

    @commands.command()
    async def remove(self, ctx: commands.Context, *, idx: int):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        title = status.queue[idx - 1][0].title
        status.queue.remove(idx - 1)
        return await ctx.send(f'{title}を削除しました')

    @commands.command()
    async def loop(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if status.loop:
            status.loop = False
            return await ctx.send('loopを無効にしました')
        else:
            status.loop = True
            return await ctx.send('loopを有効にしました')

    @commands.command()
    async def loopqueue(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if status.loopqueue:
            status.loopqueue = False
            return await ctx.send('loopqueueを無効にしました')
        else:
            status.loopqueue = True
            return await ctx.send('loopqueueを有効にしました')


def setup(bot):
    return bot.add_cog(Voice(bot))
