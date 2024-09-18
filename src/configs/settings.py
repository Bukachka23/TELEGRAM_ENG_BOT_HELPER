import os

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AudioSettings:
    AUDIOS_DIR = "audios"
    VOICE_FILE = "voice.ogg"


class OpenaiSettings:
    OPENAI_MODEL = 'gpt-4o-mini'
    WHISPER_MODEL = "whisper-1"
    DEFAULT_TEMPERATURE = 0.5
    GRAMMAR_CHECK_TEMPERATURE = 0.3
    QUIZ_GENERATION_TEMPERATURE = 0.5


class DatabaseSettings:
    DEFAULT_WORD_FILE_PATH = Path('src/data/words.txt')

    @classmethod
    def get_word_file_path(cls) -> Path:
        if cls.DEFAULT_WORD_FILE_PATH.exists():
            return cls.DEFAULT_WORD_FILE_PATH

        current_dir_path = Path(os.getcwd()) / 'words.txt'
        if current_dir_path.exists():
            return current_dir_path

        parent_dir_path = Path(os.getcwd()).parent / 'words.txt'
        if parent_dir_path.exists():
            return parent_dir_path

        return cls.DEFAULT_WORD_FILE_PATH


class EnvSettings:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ADMIN_ID = os.getenv('ADMIN_ID')
    USER_ID = os.getenv('USER_ID')
    AWS_REGION = os.getenv('AWS_REGION')


class TelegramData:
    ANSWER = 1
    SCHEDULE_INTERVAL = 1