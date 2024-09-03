import random
from typing import Optional, List
import logging
from pathlib import Path

from src.configs.config import DatabaseSettings


class WordDatabase:
    def __init__(self, file_path: Path = None):
        self.file_path: Path = file_path or DatabaseSettings.get_word_file_path()
        self.words: List[str] = []
        self.load_words()

    def load_words(self) -> None:
        """
        Load words from the specified file path.

        This method reads words from the file, strips whitespace, and stores them in memory.
        It also logs the number of loaded words or any errors encountered during the process.
        """
        try:
            with self.file_path.open('r', encoding='utf-8') as file:
                self.words = [line.strip() for line in file if line.strip()]
            logging.info(f"Loaded {len(self.words)} words from {self.file_path}")
        except FileNotFoundError:
            logging.error(f"Word file not found: {self.file_path}")
        except Exception as e:
            logging.error(f"Error reading word file: {e}")

    def get_random_word(self) -> Optional[str]:
        """
        Return a random word from the loaded list of words.

        If the word list is empty, returns None.
        """
        return random.choice(self.words) if self.words else None

    def reload_words(self) -> None:
        """Reload words from the file."""
        self.load_words()

    def add_word(self, word: str) -> None:
        """
        Add a new word to the database.

        This method adds the word to both the in-memory list and the file.
        """
        if word.strip() and word not in self.words:
            self.words.append(word.strip())
            try:
                with self.file_path.open('a', encoding='utf-8') as file:
                    file.write(f"\n{word}")
                logging.info(f"Added new word: {word}")
            except Exception as e:
                logging.error(f"Error adding word to file: {e}")

    def remove_word(self, word: str) -> bool:
        """
        Remove a word from the database.

        This method removes the word from both the in-memory list and the file.
        Returns True if the word was removed, False otherwise.
        """
        if word in self.words:
            self.words.remove(word)
            try:
                with self.file_path.open('w', encoding='utf-8') as file:
                    file.write('\n'.join(self.words))
                logging.info(f"Removed word: {word}")
                return True
            except Exception as e:
                logging.error(f"Error removing word from file: {e}")
                self.words.append(word)
        return False
