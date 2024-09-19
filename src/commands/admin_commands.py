import logging.config
import os
import sys

from telegram import Update
from telegram.ext import CallbackContext

from src.configs.log_config import LOGGING
from src.utils import helpers
from src.utils.decorators import admin_only

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class AdminCommands:
    def __init__(self, application):
        self.application = application
        self.log_command = helpers.log_command

    @admin_only
    async def restart_bot(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /restart command. Restart the bot application.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "restart")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Restarting...")

        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            logger.error(f"Error restarting bot: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Restart failed: {e}"
            )
