import asyncio
import glob
import os
import random
import re
from typing import Dict

import discord
import youtube_dl
from discord.ext import commands
from dotenv import load_dotenv
from gaato_bot.core.bot import GaatoBot
from googleapiclient.discovery import build


load_dotenv(verbose=True)
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

def get_videos_search(keyword):
    youtube = build('youtube', 'v3', developerKey=GOOGLE_API_KEY)
    youtube_query = youtube.search().list(q=keyword, part='id,snippet', maxResults=1)
    youtube_res = youtube_query.execute()
    return youtube_res.get('items', [])

def get_videos_from_playlist(playlist_id):
    youtube = build('youtube', 'v3', developerKey=GOOGLE_API_KEY)
    yotube_query = youtube.playlistItems().list(playlistId=playlist_id, part='snippet,contentDetails', maxResults=50)
    youtube_res = yotube_query.execute()
    return youtube_res.get('items', [])

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
        self.done = asyncio.Event()
        self.loop = False
        self.loopqueue = False
        asyncio.create_task(self.playing_task())

    async def add_audio(self, video):
        await self.queue.put(video)

    def get_list(self):
        return self.queue.to_list()

    async def playing_task(self):
        while True:
            try:
                video = await asyncio.wait_for(self.queue.get(), timeout=180)
            except asyncio.TimeoutError:
                asyncio.create_task(self.leave())
            while True:
                self.done.clear()
                player = await YTDLSource.from_url(video['url'], loop=client.loop)
                self.vc.play(player, after=self.play_next)
                await self.ctx.send(f'{video["title"]}を再生します...')
                await self.done.wait()
                if self.loop:
                    player = await YTDLSource.from_url(video['url'], loop=client.loop)
                elif self.loopqueue:
                    await self.add_audio(video)
                    break
                else:
                    break

    def play_next(self, err=None):
        self.done.set()

    async def leave(self):
        self.queue.reset()
        if self.vc:
            await self.vc.disconnect()
            self.vc = None
        flag = True
        for g in client.guilds:
            if g.voice_client is not None:
                flag = False
        if flag:
            for p in glob.glob('youtube-*'):
                if os.path.isfile(p):
                    os.remove(p)

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

    @commands.command(aliases=['p'])
    async def play(self, ctx: commands.Context, *, url_or_keyword: str):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            await ctx.invoke(self.join)
            status = self.audio_statuses[ctx.guild.id]
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        if re.match(r'https?://(((www|m)\.)?youtube\.com/watch\?v=|youtu\.be/)', url_or_keyword):
            result = get_videos_search(url_or_keyword)
            videos = [{
                'title': result[0]['snippet']['title'],
                'url': 'https://www.youtube.com/watch?v=' + result[0]['id']['videoId'],
                'thumbnail': result[0]['snippet']['thumbnails']['default']['url'],
                'user': ctx.author,
            }]
        elif m := re.match(r'https?://((www|m)\.)?youtube\.com/playlist\?list=', url_or_keyword):
            playlist_id = url_or_keyword.replace(m.group(), '')
            result = get_videos_from_playlist(playlist_id)
            videos = []
            for r in result:
                videos.append({
                    'title': r['snippet']['title'],
                    'url': 'https://www.youtube.com/watch?v=' + r['contentDetails']['videoId'],
                    'thumbnail': r['snippet']['thumbnails']['default']['url'],
                    'user': ctx.author,
                })
        else:
            result = get_videos_search(url_or_keyword)
            videos = [{
                'title': result[0]['snippet']['title'],
                'url': 'https://www.youtube.com/watch?v=' + result[0]['id']['videoId'],
                'thumbnail': result[0]['snippet']['thumbnails']['default']['url'],
                'user': ctx.author,
            }]
        for video in videos:
            await status.add_audio(video)
        if len(videos) == 1:
            await ctx.send(f'{videos[0]["title"]}を再生リストに追加しました')
        else:
            await ctx.send(f'{len(videos)}曲を再生リストに追加しました')

    @commands.command(aliases=['s'])
    async def skip(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        if not status.is_playing:
            return await ctx.send('既に停止しています')
        await status.skip()
        await ctx.send('スキップしました')

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('ボイスチャンネルにまだ未参加です')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        await status.leave()
        del self.audio_statuses[ctx.guild.id]

    @commands.command(aliases=['q'])
    async def queue(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('先にボイスチャンネルに参加してください')
        queue = status.get_list()
        songs = ''
        for i, video in enumerate(queue):
            songs += f'{i + 1}. {video["title"]}\n'
            if i >= 19:
                songs += '...'
                break
        await ctx.send(songs)

    @commands.command()
    async def shuffle(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        status.queue.shuffle()
        return await ctx.send('シャッフルしました')

    @commands.command(aliases=['rm'])
    async def remove(self, ctx: commands.Context, *, idx: int):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        title = status.queue[idx - 1][0].title
        status.queue.remove(idx - 1)
        return await ctx.send(f'{title}を削除しました')

    @commands.command()
    async def loop(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        if status.loop:
            status.loop = False
            return await ctx.send('loopを無効にしました')
        else:
            status.loop = True
            return await ctx.send('loopを有効にしました')

    @commands.command(aliases=['lq'])
    async def loopqueue(self, ctx: commands.Context):
        status = self.audio_statuses.get(ctx.guild.id)
        if status is None:
            return await ctx.send('Botはまだボイスチャンネルに参加していません')
        if ctx.author.voice is None or ctx.author.voice.channel.id != status.vc.channel.id:
            return await ctx.send('Botと同じボイスチャンネルに入ってください')
        if status.loopqueue:
            status.loopqueue = False
            return await ctx.send('loopqueueを無効にしました')
        else:
            status.loopqueue = True
            return await ctx.send('loopqueueを有効にしました')


def setup(bot):
    return bot.add_cog(Voice(bot))
