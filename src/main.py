import logging.config

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.configs.config import AudioSettings
from src.configs.helpers import create_dir_if_not_exists
from src.telegram_bot.bot import TelegramBot
from src.configs.log_config import LOGGING


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


def main() -> None:
    create_dir_if_not_exists(AudioSettings.AUDIOS_DIR)
    bot = TelegramBot()
    app = bot.application

    scheduler = AsyncIOScheduler()
    scheduler.add_job(bot.scheduled_quiz, 'interval', minutes=1, args=[app])
    scheduler.start()

    app.run_polling()


if __name__ == "__main__":
    main()
