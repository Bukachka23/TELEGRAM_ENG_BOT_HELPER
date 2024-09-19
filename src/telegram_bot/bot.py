import logging.config

import psutil
from tenacity import retry, stop_after_attempt, wait_exponential

from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from src.audio.speech_engine import SpeechEngine
from src.commands.admin_commands import AdminCommands
from src.commands.general_commands import GeneralCommands
from src.commands.quiz_commands import QuizCommands
from src.commands.system_commands import SystemCommands
from src.configs.log_config import LOGGING
from src.configs.settings import EnvSettings, TelegramData
from src.database.word_database import WordDatabase
from src.handlers.message_handlers import MessageHandlers
from src.handlers.voice_handlers import VoiceHandlers
from src.open_ai.openai_engine import OpenAIEngine

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class TelegramBot:
    """A Telegram bot for English tutoring, utilizing OpenAI and speech processing."""

    def __init__(self):
        """Initialize the TelegramBot with necessary components and handlers."""
        self.ai_engine = OpenAIEngine()
        self.speech_engine = SpeechEngine()
        self.word_database = {
            'english': WordDatabase('english'),
            'german': WordDatabase('german')
        }

        self.application = self._create_application_with_retry()
        self._setup_handlers()
        self.bot = self.application.bot  # type: ignore[attr-defined]

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _create_application_with_retry(self) -> Application:
        """
        Create the Telegram Application with retry logic to handle connection issues.

        Returns:
            Application: The Telegram Application instance.
        """
        logger.info("Creating Telegram application with retry...")
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=180,
            read_timeout=180
        )
        return Application.builder() \
            .token(EnvSettings.TELEGRAM_BOT_TOKEN) \
            .request(request) \
            .build()

    def _setup_handlers(self) -> None:
        """Setup command and message handlers for the Telegram bot."""
        general_commands = GeneralCommands(self.ai_engine, self.speech_engine, self.word_database)
        system_commands = SystemCommands(self.ai_engine, self.speech_engine, self.word_database)
        admin_commands = AdminCommands(self.application)
        quiz_commands = QuizCommands(self.ai_engine, self.speech_engine, self.application)
        message_handlers = MessageHandlers(self.ai_engine, self.speech_engine, self.word_database)
        voice_handlers = VoiceHandlers(self.ai_engine, self.speech_engine)

        self.application.add_handler(CommandHandler('start', system_commands.start))
        self.application.add_handler(CommandHandler('help', system_commands.help))
        self.application.add_handler(CommandHandler('send_vocab', general_commands.send_vocab))
        self.application.add_handler(CommandHandler('meaning', general_commands.meaning))
        self.application.add_handler(CommandHandler('set_language', general_commands.set_language))
        self.application.add_handler(CommandHandler('ping', system_commands.ping))
        self.application.add_handler(CommandHandler('stats', system_commands.stats))
        self.application.add_handler(CommandHandler('translate', general_commands.translate_text))
        self.application.add_handler(CommandHandler('grammar_check', general_commands.grammar_check))
        self.application.add_handler(CommandHandler('email', general_commands.email))
        self.application.add_handler(CommandHandler('essay', general_commands.essay))
        self.application.add_handler(CommandHandler('rewrite', general_commands.rewrite))
        self.application.add_handler(CommandHandler('quiz', quiz_commands.quiz))
        self.application.add_handler(CommandHandler('ticket', general_commands.ticket))
        self.application.add_handler(CommandHandler('compose', general_commands.compose))
        self.application.add_handler(CommandHandler('subscribe_quiz', quiz_commands.subscribe_quiz))
        self.application.add_handler(CommandHandler('unsubscribe_quiz', quiz_commands.unsubscribe_quiz))
        self.application.add_handler(CommandHandler('letter', general_commands.letter))
        self.application.add_handler(CommandHandler('summarize', general_commands.summarise))
        self.application.add_handler(CommandHandler('pronounce', general_commands.pronounce))
        self.application.add_handler(CommandHandler('start_speech_practice', general_commands.start_speech_practice))

        self.application.add_handler(CommandHandler('restart', admin_commands.restart_bot))

        self.application.add_handler(MessageHandler(filters.VOICE, voice_handlers.handle_voice))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handlers.check_answer))

        quiz_conversation = ConversationHandler(
            entry_points=[CommandHandler('quiz', quiz_commands.quiz)],
            states={
                TelegramData.ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, message_handlers.check_answer)],
            },
            fallbacks=[CommandHandler('cancel', quiz_commands.cancel_quiz)],
            name="quiz_conversation",
            persistent=False,
        )
        self.application.add_handler(quiz_conversation)

    async def _log_system_info(self) -> None:
        """
        Log system and bot information, including CPU, memory, and disk usage.
        """
        try:
            bot_info = await self.bot.get_me()
            if bot_info:
                logger.info(f"Logged in as @{bot_info.username}")
            else:
                logger.error("Failed to retrieve bot information.")

            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent

            system_stats = (
                f"CPU: {cpu_usage}% {'🔥' if cpu_usage > 80 else ''} | "
                f"Memory: {memory_usage}% {'☁' if memory_usage > 80 else ''} | "
                f"Disk: {disk_usage}% {'💾' if disk_usage > 80 else ''}"
            )
            logger.info(system_stats)
        except Exception as e:
            logger.error(f"Error logging system info: {e}")
