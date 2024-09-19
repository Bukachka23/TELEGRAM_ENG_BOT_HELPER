from typing import Optional

import logging.config

from telegram import Update
from telegram.ext import CallbackContext

from src.configs.log_config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


def extract_command_text(message_text: str, command: str) -> Optional[str]:
    """
    Extract the text following a command.

    Args:
        message_text (str): The complete message text.
        command (str): The command to extract text for.

    Returns:
        Optional[str]: The extracted text or None if not present.
    """
    text = message_text.replace(command, "").strip()
    return text if text else None


def get_target_language(context: CallbackContext) -> str:
    """Get the user's preferred target language.
    Args:
        context (CallbackContext): Contextual information.

    Returns:
        str: The user's preferred target language."""
    return context.user_data.get('target_language', 'ukrainian').lower()


def log_command(update: Update, command: str) -> None:
    """
    Log the invocation of a command by a user.

    Args:
        update (Update): Incoming update.
        command (str): The command that was invoked.
    """
    username = update.effective_user.username or "Unknown User"
    logger.info(f"/{command} invoked by @{username}")
