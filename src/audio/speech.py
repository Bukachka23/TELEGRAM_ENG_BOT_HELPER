import logging.config
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

import gtts
import pydub
from openai import OpenAI

from src.configs.config import AudioSettings, EnvSettings, OpenaiSettings
from src.configs.log_config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class SpeechEngine:
    def __init__(self):
        self.client = None
        self.initialize_openai_client()

    def initialize_openai_client(self):
        try:
            self.client = OpenAI(api_key=EnvSettings.OPENAI_API_KEY)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    @staticmethod
    def generate_uuid():
        uuid_value = uuid.uuid4()
        return f"{str(uuid_value)}"

    async def convert_text_to_speech(self, text: str, language_code: str = 'en', tld: str = 'com') -> str:
        """Convert text to speech and save as MP3."""
        output_filepath = os.path.join(AudioSettings.AUDIOS_DIR, f"{self.generate_uuid()}.mp3")
        try:
            tts = gtts.gTTS(text=text, lang=language_code, tld=tld)
            tts.save(output_filepath)
            return output_filepath
        except Exception as e:
            logger.error(f"Failed to convert text to speech: {e}")
            raise

    async def convert_speech_to_text(self, audio_filepath: str) -> str:
        """Convert speech to text using Whisper model."""
        try:
            with open(audio_filepath, "rb") as audio:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio
                )
            return transcript.text
        except Exception as e:
            logger.error(f"Failed to convert speech to text: {e}")
            raise

    @asynccontextmanager
    async def download_voice_as_ogg(self, voice: Any):
        """Download voice message as OGG file."""
        voice_file = await voice.get_file()
        ogg_filepath = os.path.join(AudioSettings.AUDIOS_DIR, f"{self.generate_uuid()}.ogg")
        try:
            await voice_file.download_to_drive(ogg_filepath)
            yield ogg_filepath
        finally:
            if os.path.exists(ogg_filepath):
                os.remove(ogg_filepath)

    async def convert_ogg_to_mp3(self, ogg_filepath: str) -> str:
        """Convert OGG file to MP3."""
        mp3_filepath = os.path.join(AudioSettings.AUDIOS_DIR, f"{self.generate_uuid()}.mp3")
        try:
            audio = pydub.AudioSegment.from_file(ogg_filepath, format="ogg")
            audio.export(mp3_filepath, format="mp3")
            return mp3_filepath
        except Exception as e:
            logger.error(f"Failed to convert OGG to MP3: {e}")
            raise
        finally:
            if os.path.exists(ogg_filepath):
                os.remove(ogg_filepath)

    def generate_response(self, text: str) -> str:
        """Generate a response using GPT-4 model."""
        try:
            response = self.client.chat.completions.create(
                model=OpenaiSettings.OPENAI_MODEL,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return "Sorry, an error occurred while generating the response."
