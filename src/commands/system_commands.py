import logging.config
import time

import psutil
from telegram import Update
from telegram.ext import CallbackContext

from src.configs.log_config import LOGGING
from src.utils import helpers

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class SystemCommands:
    def __init__(self, ai_engine, speech_engine, word_database):
        self.ai_engine = ai_engine
        self.speech_engine = speech_engine
        self.word_database = word_database
        self.log_command = helpers.log_command

    async def start(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /start command. Send a welcome message to the user.
        """
        self.log_command(update, "start")
        welcome_message = (
            "Hello! I'm an English-tutor bot designed to help you improve your vocabulary.\n"
            "To get started, type /help for available commands.\n"
            "Let's expand our vocabulary together! 😊"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message)

    async def help(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /help command. Provide a list of available commands to the user.
        """
        self.log_command(update, "help")
        help_text = (
            "Available commands:\n"
            "/start - Greeting message\n"
            "/help - Show this help message\n"
            "/send_vocab - Improve vocabulary with random words\n"
            "/meaning <word> - Get definition and usage example\n"
            "/email <topic> - Compose an email\n"
            "/essay <topic> - Generate an essay\n"
            "/ping - Check bot latency\n"
            "/stats - Show system statistics\n"
            "/translate <text> - Translate to Ukrainian\n"
            "/grammar_check <text> - Check grammar\n"
            "/rewrite <text> - Rewrite text\n"
            "/quiz - Start a translation quiz\n"
            "/ticket <issue description> - Create an issue ticket\n"
            "/compose - Compose an email\n"
            "/letter - Write a letter\n"
            "/summarize <text> - Summarize text\n"
            "/pronounce <text> - Pronounce text\n"
            "/subscribe_quiz - Subscribe to hourly quizzes\n"
            "/unsubscribe_quiz - Unsubscribe from hourly quizzes\n"
            "/start_speech_practice - Start speech practice\n"
            "/set_language <language> - Set target language\n"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

    async def ping(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /ping command. Respond with the bot's latency.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "ping")
        start_time = time.time()
        message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Pinging...")
        end_time = time.time()
        latency_ms = round((end_time - start_time) * 1000, 2)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message.message_id,
            text=f"Pong! Latency is {latency_ms}ms"
        )

    @staticmethod
    async def stats(update: Update, context: CallbackContext) -> None:
        """
        Handle the /stats command. Provide system statistics to the user.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        try:
            logger.info("/stats invoked!")
            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent

            stats_message = (
                f"CPU: {cpu_usage}% {'🔥' if cpu_usage > 80 else ''}\n"
                f"Memory: {memory_usage}% {'☁' if memory_usage > 80 else ''}\n"
                f"Disk: {disk_usage}% {'💾' if disk_usage > 80 else ''}"
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=stats_message)
        except Exception as e:
            logger.error(f"Error generating stats: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"An error occurred while generating stats.\nError: {e}"
            )
