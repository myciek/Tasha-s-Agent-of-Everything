"""Discord Voice Bot for D&D Session Recording.

Joins voice channel and records audio, then transcribes it.

Usage:
    python -m src.discord_bot

Commands:
    /voice join  - Bot joins your voice channel
    /voice leave - Bot leaves voice channel and saves recording
"""

import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from src.config import SHARED_DATA_PATH

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in environment")

TRANSCRIPTS_PATH = SHARED_DATA_PATH / "recordings"
TRANSCRIPTS_PATH.mkdir(parents=True, exist_ok=True)

# Bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Recording state
recording_state = {
    "active": False,
    "voice_client": None,
    "session_name": None,
}


# Command group
voice_group = app_commands.Group(name="voice", description="Voice channel commands")


@bot.event
async def on_ready():
    """Called when bot is ready."""
    logger.info(f"Bot logged in as {bot.user}")
    await tree.sync()
    logger.info("Commands synced")


class AudioRecorder(discord.AudioSink):
    """Custom audio sink for recording to file."""
    
    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        self.file = None
        self._user_data = {}
    
    def write(self, data: bytes):
        """Write audio data to file."""
        if self.file:
            self.file.write(data)
    
    def format_audio(self, data: bytes, codec, channels, sample_rate):
        """Format raw audio data."""
        return data
    
    async def on_speaking_update(self, speaking: dict):
        """Called when speaking state changes."""
        pass


@voice_group.command(name="join", description="Join voice channel to record session")
async def voice_join(interaction: discord.Interaction, name: str = None):
    """Join the user's voice channel and start recording."""
    if recording_state["active"]:
        await interaction.response.send_message(
            "Already recording! Use `/voice leave` first.",
            ephemeral=True
        )
        return
    
    # Check if user is in a voice channel
    if not interaction.user.voice:
        await interaction.response.send_message(
            "You need to be in a voice channel first.",
            ephemeral=True
        )
        return
    
    voice_channel = interaction.user.voice.channel
    
    # Generate session name
    session_name = name or f"Session_{datetime.now().strftime('%Y%m%d_%H%M')}"
    audio_path = TRANSCRIPTS_PATH / f"{session_name}.webm"
    
    # Connect to voice
    try:
        vc = await voice_channel.connect()
    except discord.ClientException as e:
        await interaction.response.send_message(
            f"Could not connect: {e}",
            ephemeral=True
        )
        return
    
    # Create audio sink
    sink = AudioRecorder(str(audio_path))
    sink.file = open(str(audio_path), 'wb')
    
    # Update state
    recording_state["active"] = True
    recording_state["voice_client"] = vc
    recording_state["session_name"] = session_name
    recording_state["audio_sink"] = sink
    
    # Start recording
    vc.start_recording(sink, lambda s, c: logger.info("Recording callback"))
    
    logger.info(f"Started recording: {session_name} in {voice_channel.name}")
    
    await interaction.response.send_message(
        f"Recording started: **{session_name}**\n"
        f"Channel: {voice_channel.name}\n"
        f"Use `/voice leave` when done to save.",
        ephemeral=True
    )


@voice_group.command(name="leave", description="Leave voice channel and save recording")
async def voice_leave(interaction: discord.Interaction):
    """Stop recording and leave voice channel."""
    if not recording_state["active"]:
        await interaction.response.send_message(
            "Not currently recording.",
            ephemeral=True
        )
        return
    
    vc = recording_state["voice_client"]
    session_name = recording_state["session_name"]
    audio_path = TRANSCRIPTS_PATH / f"{session_name}.webm"
    
    # Stop recording
    vc.stop_recording()
    
    # Close file
    if recording_state.get("audio_sink") and recording_state["audio_sink"].file:
        recording_state["audio_sink"].file.close()
    
    await vc.disconnect()
    
    # Reset state
    recording_state["active"] = False
    recording_state["voice_client"] = None
    
    logger.info(f"Stopped recording: {session_name}")
    
    # Check if file was created
    if audio_path.exists():
        size_mb = audio_path.stat().st_size / (1024 * 1024)
        await interaction.response.send_message(
            f"Recording saved: **{session_name}**\n"
            f"File: `{audio_path.name}` ({size_mb:.1f} MB)\n\n"
            f"To transcribe, run:\n"
            f"`python -m src.discord_bot transcribe {session_name}`"
        )
    else:
        await interaction.response.send_message(
            f"Recording stopped but file not found."
        )


@voice_group.command(name="cancel", description="Cancel recording without saving")
async def voice_cancel(interaction: discord.Interaction):
    """Cancel recording without saving."""
    if not recording_state["active"]:
        await interaction.response.send_message(
            "Not currently recording.",
            ephemeral=True
        )
        return
    
    session_name = recording_state["session_name"]
    audio_path = TRANSCRIPTS_PATH / f"{session_name}.webm"
    
    # Stop and disconnect
    recording_state["voice_client"].stop_recording()
    await recording_state["voice_client"].disconnect()
    
    # Close and delete file
    if recording_state.get("audio_sink") and recording_state["audio_sink"].file:
        recording_state["audio_sink"].file.close()
    if audio_path.exists():
        audio_path.unlink()
    
    # Reset state
    recording_state["active"] = False
    
    await interaction.response.send_message(
        f"Cancelled recording: **{session_name}**"
    )


# Register commands
tree.add_command(voice_group)


def run():
    """Run the bot."""
    logger.info("Starting Discord voice bot...")
    logger.info(f"Recordings will be saved to: {TRANSCRIPTS_PATH}")
    bot.run(DISCORD_TOKEN)


async def transcribe_recording(audio_path: Path, session_name: str):
    """Transcribe a recording using Whisper."""
    logger.info(f"Transcribing {audio_path.name}...")
    
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path), language="pl")
    
    transcript_path = TRANSCRIPTS_PATH / f"{session_name}.md"
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(f"# {session_name}\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write(f"**Duration**: {result.get('duration', 'N/A')} seconds\n\n")
        f.write("---\n\n")
        f.write("## Transcript\n\n")
        f.write(result["text"])
    
    logger.info(f"Transcription saved: {transcript_path}")
    return transcript_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "transcribe":
        # CLI transcription mode
        name = sys.argv[2] if len(sys.argv) > 2 else None
        audio_path = TRANSCRIPTS_PATH / f"{name}.webm" if name else None
        
        if not audio_path or not audio_path.exists():
            # Find most recent
            files = sorted(TRANSCRIPTS_PATH.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                audio_path = files[0]
                name = audio_path.stem
            else:
                print("No recordings found!")
                exit(1)
        
        print(f"Transcribing {audio_path.name}... (this will take a while)")
        
        import asyncio
        result_path = asyncio.run(transcribe_recording(audio_path, name))
        
        print(f"Done! Saved to: {result_path}")
        print(f"Run agent: python -m src.cli {result_path.name}")
    else:
        run()
