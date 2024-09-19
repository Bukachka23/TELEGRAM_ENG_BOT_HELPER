import os

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AudioSettings:
    AUDIOS_DIR: Path = Path("audios")
    VOICE_FILE: Path = Path("voice.ogg")


class OpenaiSettings:
    OPENAI_MODEL = 'gpt-4o-mini'
    WHISPER_MODEL = "whisper-1"
    DEFAULT_TEMPERATURE = 0.5
    GRAMMAR_CHECK_TEMPERATURE = 0.3
    QUIZ_GENERATION_TEMPERATURE = 0.5


class DatabaseSettings:
    WORD_FILES = {
        'english': Path('/Users/ihortresnystkyi/Documents/ENG_BOT/src/data/eng_words.txt'),
        'german': Path('/Users/ihortresnystkyi/Documents/ENG_BOT/src/data/ger_words.txt'),
    }

    @classmethod
    def get_word_file_path(cls, language: str) -> Path:
        file_path = cls.WORD_FILES.get(language.lower())
        if file_path and file_path.exists():
            return file_path
        else:
            raise FileNotFoundError(f"Word file for language '{language}' not found.")


class EnvSettings:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    ADMIN_ID = os.getenv('ADMIN_ID')
    USER_ID = os.getenv('USER_ID')
    AWS_REGION = os.getenv('AWS_REGION')


class TelegramData:
    ANSWER = 1
    SCHEDULE_INTERVAL = 1
