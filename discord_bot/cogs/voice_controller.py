"""
Voice command handler for OutreachBot.
Mohit joins #voice-control, speaks a command, bot transcribes + executes.
Uses Groq Whisper API for transcription (free tier).
MVP mode: !listen starts 10s recording session.
"""
from __future__ import annotations
import asyncio
import io
import os
import tempfile
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import discord
from discord.ext import commands

GROQ_API_KEY = os.getenv("GROQ_API_KEY","")


async def transcribe_with_groq(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Send audio to Groq Whisper API, return transcript."""
    if not GROQ_API_KEY:
        return ""
    try:
        import aiohttp
        form = aiohttp.FormData()
        form.add_field("file", audio_bytes, filename=filename, content_type="audio/wav")
        form.add_field("model", "whisper-large-v3")
        form.add_field("language", "en")
        form.add_field("response_format", "text")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    return (await resp.text()).strip()
    except Exception as e:
        print(f"[VoiceController] Transcription error: {e}")
    return ""


try:
    _SinkBase = discord.sinks.AudioSink
except AttributeError:
    _SinkBase = object  # Fallback if sinks not available


class AudioSink(_SinkBase):
    """Records audio from a voice channel."""
    def __init__(self):
        self.audio_data: dict[int, list[bytes]] = {}

    def write(self, user, data):
        uid = getattr(user, "id", 0)
        if uid not in self.audio_data:
            self.audio_data[uid] = []
        pcm = getattr(data, "pcm", data) if not isinstance(data, bytes) else data
        self.audio_data[uid].append(pcm)

    def cleanup(self):
        pass


class VoiceController(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._voice_client: discord.VoiceClient | None = None
        self._listening = False
        self._commands_channel: discord.TextChannel | None = None

    async def _get_commands_channel(self) -> discord.TextChannel | None:
        if self._commands_channel:
            return self._commands_channel
        ch_id = os.getenv("DISCORD_COMMANDS_CHANNEL_ID")
        if ch_id:
            ch = self.bot.get_channel(int(ch_id))
            if ch:
                self._commands_channel = ch
                return ch
        return None

    @commands.command(name="join")
    async def join_voice(self, ctx: commands.Context):
        """Bot joins your voice channel."""
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel first.")
            return
        vc = ctx.author.voice.channel
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.move_to(vc)
        else:
            self._voice_client = await vc.connect()
        await ctx.send(embed=discord.Embed(
            title=f"🎤 Joined: {vc.name}",
            description=(
                "I'm in the voice channel. Use `!listen` to start recording.\n"
                "Speak your command, then type `!listen` again or wait 10 seconds.\n\n"
                "**Voice command examples:**\n"
                "• \"Enrich 5 leads\"\n"
                "• \"Show me Arya's messages\"\n"
                "• \"What's my pipeline status?\"\n"
                "• \"Move Etai to connected\"\n"
                "• \"Kitni leads enriched hain?\""
            ),
            color=discord.Color.green(),
        ))

    @commands.command(name="leave")
    async def leave_voice(self, ctx: commands.Context):
        """Bot leaves voice channel."""
        if self._voice_client and self._voice_client.is_connected():
            await self._voice_client.disconnect()
            self._voice_client = None
            await ctx.send("👋 Left voice channel.")
        else:
            await ctx.send("Not in a voice channel.")

    @commands.command(name="listen")
    async def listen_cmd(self, ctx: commands.Context, duration: int = 10):
        """Start voice recording for N seconds (default 10). Speak your command."""
        if not self._voice_client or not self._voice_client.is_connected():
            await ctx.send("❌ I'm not in a voice channel. Type `!join` first.")
            return

        if self._listening:
            await ctx.send("⏳ Already listening. Wait for current recording to finish.")
            return

        self._listening = True
        msg = await ctx.send(embed=discord.Embed(
            title=f"🎙️ Listening for {duration}s...",
            description="Speak your command clearly. I'll transcribe and execute it.",
            color=discord.Color.blue(),
        ))

        # Try using discord.py audio sink (requires PyNaCl)
        try:
            sink = AudioSink()
            self._voice_client.start_recording(sink, self._recording_finished, ctx, msg)
            await asyncio.sleep(duration)
            self._voice_client.stop_recording()
        except AttributeError:
            # Fallback: voice receive not available without extra setup
            self._listening = False
            await msg.edit(embed=discord.Embed(
                title="⚠️ Voice receive not available",
                description=(
                    "Voice recording requires additional setup:\n"
                    "1. `pip install PyNaCl`\n"
                    "2. `brew install ffmpeg` (macOS)\n"
                    "3. Restart the bot\n\n"
                    "**Alternative:** Type commands directly — natural language works too!\n"
                    "Example: `kitni leads enriched hain?`"
                ),
                color=discord.Color.orange(),
            ))
        except Exception as e:
            self._listening = False
            await msg.edit(embed=discord.Embed(
                title="❌ Recording error",
                description=f"```{e}```\nMake sure ffmpeg is installed: `brew install ffmpeg`",
                color=discord.Color.red(),
            ))

    async def _recording_finished(self, sink: AudioSink, ctx: commands.Context, status_msg: discord.Message, *args):
        """Called when recording finishes — transcribe and execute."""
        self._listening = False
        try:
            # Get audio from the primary speaker (first user found)
            if not sink.audio_data:
                await status_msg.edit(embed=discord.Embed(
                    title="🎤 No audio detected",
                    description="Nothing was recorded. Try speaking louder or closer to mic.",
                    color=discord.Color.orange(),
                ))
                return

            # Combine all audio for the first user
            uid    = list(sink.audio_data.keys())[0]
            frames = sink.audio_data[uid]
            pcm    = b"".join(frames)

            # Convert raw PCM to WAV
            audio_wav = self._pcm_to_wav(pcm)

            await status_msg.edit(embed=discord.Embed(
                title="🔄 Transcribing...",
                color=discord.Color.blue(),
            ))

            transcript = await transcribe_with_groq(audio_wav)
            if not transcript:
                await status_msg.edit(embed=discord.Embed(
                    title="❌ Transcription failed",
                    description=(
                        "Could not transcribe audio.\n"
                        "Check GROQ_API_KEY in .env\n"
                        "Or type commands directly in chat."
                    ),
                    color=discord.Color.red(),
                ))
                return

            await status_msg.edit(embed=discord.Embed(
                title="🎤 Heard",
                description=f'`"{transcript}"`\n\n⚙️ Processing...',
                color=discord.Color.green(),
            ))

            # Post transcript to commands channel + execute
            ch = await self._get_commands_channel() or ctx.channel
            await ch.send(f"🎤 Voice: `\"{transcript}\"`")

            # Inject as a regular message for NL processing
            fake_msg = ctx.message
            fake_msg.content = transcript
            await self.bot.process_commands(fake_msg)

            # Also trigger NL parser directly
            nl_cog = self.bot.cogs.get("NaturalLanguage")
            if nl_cog:
                fake = type('FakeMsg', (), {
                    'author': ctx.author, 'channel': ch,
                    'content': transcript, 'bot': False,
                })()
                await nl_cog.on_message(fake)

        except Exception as e:
            print(f"[VoiceController] Recording error: {e}")
            await status_msg.edit(embed=discord.Embed(
                title="❌ Error processing audio",
                description=str(e),
                color=discord.Color.red(),
            ))

    @staticmethod
    def _pcm_to_wav(pcm: bytes, sample_rate: int = 48000, channels: int = 2) -> bytes:
        """Convert raw PCM bytes to WAV format."""
        import struct
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        data_size = len(pcm)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE",
            b"fmt ", 16, 1, channels, sample_rate,
            byte_rate, block_align, bits_per_sample,
            b"data", data_size,
        )
        return header + pcm

    @commands.command(name="voice_test")
    async def test_transcribe(self, ctx: commands.Context, *, text: str):
        """Simulate a voice command (for testing). !voice_test enrich 5 leads"""
        await ctx.send(embed=discord.Embed(
            title="🎤 Voice Simulation",
            description=f"Simulating voice command: `\"{text}\"`",
            color=discord.Color.blue(),
        ))
        # Dispatch through NL parser
        nl_cog = self.bot.cogs.get("NaturalLanguage")
        if nl_cog:
            # Temporarily modify message content
            orig = ctx.message.content
            ctx.message.content = text
            await nl_cog.on_message(ctx.message)
            ctx.message.content = orig


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceController(bot))
