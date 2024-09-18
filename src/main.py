import logging.config
import signal
import sys
from typing import NoReturn

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

from src.configs.settings import AudioSettings, TelegramData
from src.configs.helpers import create_dir_if_not_exists
from src.telegram_bot.bot import TelegramBot
from src.configs.log_config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


def signal_handler(signum, frame):
    """Handle SIGINT and SIGTERM signals for graceful shutdown."""
    logger.info(f"Received signal {signum}. Shutting down...")
    sys.exit(0)


def main() -> NoReturn:
    try:
        logger.info("Starting main function...")
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Creating necessary directories...")
        create_dir_if_not_exists(AudioSettings.AUDIOS_DIR)

        logger.info("Initializing Telegram bot...")
        bot = TelegramBot()
        app = bot.application

        logger.info("Setting up scheduler...")
        executors = {
            'default': AsyncIOExecutor()
        }
        scheduler = AsyncIOScheduler(executors=executors)
        scheduler.add_job(bot.scheduled_quiz, 'interval', minutes=TelegramData.SCHEDULE_INTERVAL)

        scheduler.start()

        logger.info("Starting Telegram bot polling...")
        app.run_polling()

    except Exception as e:
        logger.error(f"An error occurred in the main function: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
