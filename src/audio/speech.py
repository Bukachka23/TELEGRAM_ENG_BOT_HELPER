import logging.config
import os
import uuid

import gtts
import pydub
from openai import OpenAI

from src.configs.config import AudioSettings, EnvSettings
from src.configs.log_config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class SpeechEngine:

    def __init__(self):
        self.client = OpenAI(api_key=EnvSettings.OPENAI_API_KEY)

    def convert_text_to_speech(self, text, language_code='en', tld='com'):
        output_filepath = os.path.join(AudioSettings.AUDIOS_DIR, f"{self.generate_unique_name()}.mp3")
        tts = gtts.gTTS(text=text, lang=language_code, tld=tld)
        tts.save(output_filepath)
        return output_filepath

    @staticmethod
    def generate_unique_name():
        uuid_value = uuid.uuid4()
        return f"{str(uuid_value)}"

    def convert_speech_to_text(self, audio_filepath):
        with open(audio_filepath, "rb") as audio:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio)
            return transcript.text

    async def download_voice_as_ogg(self, voice):
        voice_file = await voice.get_file()
        ogg_filepath = os.path.join(AudioSettings.AUDIOS_DIR, f"{self.generate_unique_name()}.ogg")
        await voice_file.download_to_drive(ogg_filepath)
        return ogg_filepath

    def convert_ogg_to_mp3(self, ogg_filepath):
        mp3_filepath = os.path.join(AudioSettings.AUDIOS_DIR, f"{self.generate_unique_name()}.mp3")
        audio = pydub.AudioSegment.from_file(ogg_filepath, format="ogg")
        audio.export(mp3_filepath, format="mp3")
        return mp3_filepath

    def generate_response(self, text):
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(e)
            return "Sorry, an error occurred while generating the response."
