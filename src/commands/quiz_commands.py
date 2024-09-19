import logging.config
import os
import time

import aiofiles
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler

from src.configs.log_config import LOGGING
from src.utils import helpers

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class QuizCommands:
    def __init__(self, ai_engine, speech_engine, application):
        self.ai_engine = ai_engine
        self.bot = application.bot
        self.speech_engine = speech_engine
        self.application = application
        self.log_command = helpers.log_command
        self.get_target_language = helpers.get_target_language

    async def quiz(self, update: Update, context: CallbackContext) -> int:
        """
        Handle the /quiz command. Start a translation quiz session.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.

        Returns:
            int: The next state in the conversation.
        """
        self.log_command(update, "quiz")
        target_language = self.get_target_language(context)
        quiz_data = await self.ai_engine.generate_quiz_question()
        if not quiz_data:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Sorry, I couldn't generate a quiz question for {target_language.capitalize()} at the moment."
            )
            return ConversationHandler.END

    @staticmethod
    async def subscribe_quiz(update: Update, context: CallbackContext) -> None:
        """
        Handle the subscription to hourly quizzes.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        logger.info("Subscribe quiz method called.")
        chat_id = update.effective_chat.id
        subscribed_users = context.bot_data.setdefault('subscribed_users', [])

        if chat_id not in subscribed_users:
            subscribed_users.append(chat_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text="You've successfully subscribed to hourly quizzes!"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="You're already subscribed to hourly quizzes."
            )

    @staticmethod
    async def unsubscribe_quiz(update: Update, context: CallbackContext) -> None:
        """
        Handle the unsubscription from hourly quizzes.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        logger.info("Unsubscribe quiz method called.")
        chat_id = update.effective_chat.id
        subscribed_users = context.bot_data.get('subscribed_users', [])

        if chat_id in subscribed_users:
            subscribed_users.remove(chat_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text="You've successfully unsubscribed from hourly quizzes."
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text="You're not currently subscribed to hourly quizzes."
            )

    async def scheduled_quiz(self) -> None:
        """
        Send scheduled quizzes to subscribed users.
        """
        start_time = time.time()
        logger.info("Starting scheduled quiz...")

        subscribed_users: list = self.application.bot_data.get('subscribed_users', [])

        for chat_id in subscribed_users:
            try:
                logger.info(f"Sending scheduled quiz to {chat_id}...")
                quiz_data = self.ai_engine.generate_quiz_question()

                if not quiz_data:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text="Sorry, I couldn't generate a quiz question at the moment. Please try again later."
                    )
                    continue

                audio_filepath = await self.speech_engine.convert_text_to_speech(quiz_data['english_sentence'])

                async with aiofiles.open(audio_filepath, 'rb') as audio_file:
                    audio_content = await audio_file.read()

                await self.bot.send_voice(
                    chat_id=chat_id,
                    voice=audio_content,
                    caption="Listen to the sentence and provide the correct Ukrainian translation."
                )

                os.remove(audio_filepath)

                await self.bot.send_message(
                    chat_id=chat_id,
                    text="Please type your Ukrainian translation:"
                )

                self.application.bot_data.setdefault('scheduled_quizzes', {})[chat_id] = quiz_data

            except Exception as e:
                logger.error(f"Error sending scheduled quiz to {chat_id}: {e}")

        end_time = time.time()
        logger.info(f"Scheduled quiz completed in {end_time - start_time:.2f} seconds")

    @staticmethod
    async def cancel_quiz(update: Update, context: CallbackContext) -> int:
        """
        Handle the cancellation of a quiz.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.

        Returns:
            int: Ends the conversation.
        """
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Quiz cancelled. You can start a new quiz anytime with /quiz."
        )
        return ConversationHandler.END
