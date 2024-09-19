import logging.config

from telegram import Update
from telegram.ext import ConversationHandler, CallbackContext

from src.configs.log_config import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class MessageHandlers:
    def __init__(self, ai_engine, speech_engine, word_database):
        self.ai_engine = ai_engine
        self.speech_engine = speech_engine
        self.word_database = word_database

    async def check_answer(self, update: Update, context: CallbackContext) -> int:
        """
        Check the user's answer in the quiz and provide feedback.

        Args:
            update (Update): Incoming update containing the user's answer.
            context (CallbackContext): Contextual information.

        Returns:
            int: Ends the conversation.
        """
        user_answer = update.message.text.strip().lower()
        chat_id = update.effective_chat.id

        quiz_data = context.user_data.get('quiz_data')

        if not quiz_data:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, I couldn't retrieve the quiz data. Please start a new quiz with /quiz."
            )
            return ConversationHandler.END

        correct_translation = quiz_data.get('correct_translation', '').strip().lower()

        if user_answer == correct_translation:
            result_text = "🎉 Correct! Well done!"
        else:
            result_text = (
                f"❌ Sorry, that's not correct. The right answer is:\n\n{quiz_data.get('correct_translation')}"
            )

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{result_text}\n\nEnglish sentence: {quiz_data.get('english_sentence')}"
        )

        context.user_data.pop('quiz_data', None)
        return ConversationHandler.END
