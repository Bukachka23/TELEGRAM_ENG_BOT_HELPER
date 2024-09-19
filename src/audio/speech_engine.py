import asyncio
import io
import logging.config
import os

import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Generator

import aiofiles
import gtts
import pydub
import openai

from src.configs.log_config import LOGGING
from src.configs.settings import EnvSettings, AudioSettings

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class SpeechEngine:
    """Handles speech-to-text and text-to-speech operations using OpenAI and gTTS."""
    LANGUAGE_CODES = {
        'english': 'en',
        'german': 'de',
    }

    def __init__(self):
        self.client = self.initialize_openai_client()

    def initialize_openai_client(self):
        """Initialize the OpenAI client."""
        try:
            openai.api_key = EnvSettings.OPENAI_API_KEY
            return openai
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    @staticmethod
    def generate_uuid() -> str:
        """Generate a unique UUID string."""
        return str(uuid.uuid4())

    async def convert_text_to_speech(
            self,
            text: str,
            language_code: str = 'en',
            tld: str = 'com'
    ) -> str:
        """Convert text to speech and save as MP3."""
        output_filepath = AudioSettings.AUDIOS_DIR / f"{self.generate_uuid()}.mp3"
        try:
            loop = asyncio.get_event_loop()
            tts = gtts.gTTS(text=text, lang=language_code, tld=tld)
            await loop.run_in_executor(None, tts.save, str(output_filepath))
            return str(output_filepath)
        except Exception as e:
            logger.exception("Failed to convert text to speech: %s", e)
            raise

    async def convert_speech_to_text(self, audio_filepath: str) -> str:
        """Convert speech to text using Whisper model."""
        try:
            async with aiofiles.open(audio_filepath, 'rb') as audio_file:
                audio_content = await audio_file.read()

            buffer = io.BytesIO(audio_content)
            buffer.name = os.path.basename(audio_filepath)

            loop = asyncio.get_running_loop()
            transcript = await loop.run_in_executor(
                None,
                lambda: self.client.audio.transcriptions.create(
                    file=buffer,
                    model="whisper-1"
                )
            )
            return transcript.text
        except Exception as e:
            logger.exception("Failed to convert speech to text: %s", e)
            raise

    @asynccontextmanager
    async def download_voice_as_ogg(self, voice: Any) -> Generator[str, None, None]:
        """Download voice message as OGG file."""
        ogg_filepath = AudioSettings.AUDIOS_DIR / f"{self.generate_uuid()}.ogg"
        try:
            voice_file = await voice.get_file()
            await voice_file.download_to_drive(str(ogg_filepath))
            yield str(ogg_filepath)
        except Exception as e:
            logger.exception("Failed to download voice as OGG: %s", e)
            raise
        finally:
            if ogg_filepath.exists():
                try:
                    ogg_filepath.unlink()
                except Exception as remove_err:
                    logger.error(f"Failed to remove OGG file {ogg_filepath}: {remove_err}")

    async def convert_ogg_to_mp3(self, ogg_filepath: str) -> str:
        """Convert OGG file to MP3."""
        ogg_path = AudioSettings.AUDIOS_DIR / Path(ogg_filepath).name
        mp3_filepath = AudioSettings.AUDIOS_DIR / f"{self.generate_uuid()}.mp3"
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: pydub.AudioSegment.from_file(str(ogg_path), format="ogg").export(str(mp3_filepath),
                                                                                         format="mp3")
            )
            return str(mp3_filepath)
        except Exception as e:
            logger.exception("Failed to convert OGG to MP3: %s", e)
            raise
        finally:
            if ogg_path.exists():
                try:
                    ogg_path.unlink()
                except Exception as remove_err:
                    logger.error(f"Failed to remove OGG file {ogg_path}: {remove_err}")
