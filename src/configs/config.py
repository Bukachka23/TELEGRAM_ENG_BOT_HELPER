import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AudioSettings:
    AUDIOS_DIR = "audios"
    VOICE_FILE = "voice.ogg"


class EnvSettings:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ADMIN_ID = os.getenv('ADMIN_ID')
    USER_ID = os.getenv('USER_ID')
    AWS_REGION = os.getenv('AWS_REGION')


class TelegramData:
    ANSWER = 1
