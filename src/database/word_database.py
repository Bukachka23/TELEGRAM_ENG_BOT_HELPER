import logging
import random
from pathlib import Path
from typing import Optional, List


import threading

from src.configs.settings import DatabaseSettings

logger = logging.getLogger(__name__)


class WordDatabase:
    """Handles word database operations."""

    def __init__(self, language: str):
        self.language = language
        self.file_path: Path = DatabaseSettings.get_word_file_path(language)
        self.words: List[str] = []
        self.lock = threading.Lock()
        self.load_words()

    def load_words(self) -> None:
        """Load words from the specified file path."""
        try:
            with self.file_path.open('r', encoding='utf-8') as file:
                self.words = [line.strip() for line in file if line.strip()]
            logger.info(f"Loaded {len(self.words)} words from {self.file_path}")
        except FileNotFoundError:
            logger.error(f"Word file not found: {self.file_path}")
        except Exception as e:
            logger.error(f"Error reading word file: {e}")

    def get_random_word(self) -> Optional[str]:
        """Return a random word from the loaded list of words."""
        with self.lock:
            return random.choice(self.words) if self.words else None
