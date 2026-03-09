import discord
from discord.ext import commands
import youtube_dl
import asyncio
import os
import subprocess
import sys

# Check if ffmpeg is available
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    print("✅ FFmpeg is installed and working!")
except (subprocess.CalledProcessError, FileNotFoundError):
    print("❌ FFmpeg is not installed or not in PATH")
    sys.exit(1)

TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("❌ DISCORD_TOKEN environment variable not set!")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Suppress noise
youtube_dl.utils.bug_reports_message = lambda: ''

# Configure youtube-dl
ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

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
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} has connected to Discord!')
    await bot.change_presence(activity=discord.Game(name="!play | Music Bot"))

@bot.command(name='play')
async def play(ctx, *, url):
    """Play music from YouTube"""
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in a voice channel!")
        return
    
    channel = ctx.author.voice.channel
    
    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)
    
    async with ctx.typing():
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f'🎵 Now playing: **{player.title}**')
        except Exception as e:
            await ctx.send(f"❌ Error playing song: {str(e)}")

@bot.command(name='stop')
async def stop(ctx):
    """Stop music and disconnect"""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Disconnected from voice channel")
    else:
        await ctx.send("❌ I'm not in a voice channel!")

if __name__ == "__main__":
    bot.run(TOKEN)