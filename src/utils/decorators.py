import logging.config
from functools import wraps

from telegram import Update
from telegram.ext import CallbackContext

from src.configs.log_config import LOGGING
from src.configs.settings import EnvSettings

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


def admin_only(func):
    """Decorator to check if the user is an admin.
    Args:
        func: The function to be decorated
    Returns:
        The decorated function
    """
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        if update.effective_user.id != EnvSettings.ADMIN_ID:
            logger.warning(f"Unauthorized access by user ID {update.effective_user.id}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="You are not authorized to use this command."
            )
            return
        return await func(update, context, *args, **kwargs)

    return wrapper
