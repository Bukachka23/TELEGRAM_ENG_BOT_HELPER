from telegram import Update

import os
import sys
import time
import logging.config
from typing import Optional

import aiofiles
import psutil
from tenacity import retry, stop_after_attempt, wait_exponential

from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from src.audio.speech_engine import SpeechEngine
from src.configs.log_config import LOGGING
from src.configs.settings import EnvSettings, TelegramData
from src.database.word_database import WordDatabase
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
        command_callbacks = {
            'start': self.start,
            'help': self.help,
            'send_vocab': self.send_vocab,
            'meaning': self.meaning,
            'email': self.email,
            'essay': self.essay,
            'ping': self.ping,
            'stats': self.stats,
            'restart': self.restart_bot,
            'dev': self.dev_info,
            'letter': self.letter,
            'summarise': self.summarise,
            'compose': self.compose,
            'rewrite': self.rewrite,
            'ticket': self.ticket,
            'pronounce': self.pronounce,
            'translate': self.translate_text,
            'grammar_check': self.grammar_check,
            'quiz': self.quiz,
            'subscribe_quiz': self.subscribe_quiz,
            'unsubscribe_quiz': self.unsubscribe_quiz,
            'start_speech_practice': self.start_speech_practice,
            'set_language': self.set_language
        }

        for command, callback in command_callbacks.items():
            self.application.add_handler(CommandHandler(command, callback))

        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_answer))

        quiz_conversation = ConversationHandler(
            entry_points=[CommandHandler('quiz', self.quiz)],
            states={
                TelegramData.ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_answer)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_quiz)],
            name="quiz_conversation",
            persistent=False,
        )
        self.application.add_handler(quiz_conversation)

    def get_target_language(self, context: CallbackContext) -> str:
        return context.user_data.get('target_language', 'ukrainian').lower()

    async def set_language(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /set_language command to set the user's preferred target language.
        """
        self._log_command(update, "set_language")
        language = self._extract_command_text(update.message.text, "/set_language")
        if not language:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please specify a language. Usage: /set_language <language>"
            )
            return

        if language.lower() not in ['english', 'german']:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Invalid language. Supported languages are 'english' and 'german'."
            )
            return

        context.user_data['target_language'] = language.lower()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Target language set to {language.capitalize()}."
        )

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

    async def start(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /start command. Send a welcome message to the user.
        """
        self._log_command(update, "start")
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
        self._log_command(update, "help")
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
            "/quiz - Start a translation quiz\n"
            "/subscribe_quiz - Subscribe to hourly quizzes\n"
            "/unsubscribe_quiz - Unsubscribe from hourly quizzes\n"
            "/start_speech_practice - Start speech practice"
            "/set_language <language> - Set target language"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

    async def send_vocab(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /send_vocab command. Send a random word with its definition and usage examples.
        """
        self._log_command(update, "send_vocab")
        language = self.get_target_language(context
                                            )
        word = self.word_database.get(language)
        if not word:
            logger.warning(f"No word found for language {language} database")
            await update.message.reply_text(f"Sorry, now word found in the {language} database")
            return

        if language == 'english':
            prompts = [
                f"Define '{word}' in one sentence:",
                f"Generate a sentence using '{word}'"
            ]
        else:
            prompts = [
                f"Define '{word}' in {language} in one sentence:",
                f"Generate a {language} sentence using '{word}'"
            ]

        responses = [await self.ai_engine.generate_response(prompt) for prompt in prompts]

        full_response = (
            f"Word: {word}\n"
            f"Definition: {responses[0]}\n"
            f"Example sentence: {responses[1]}"
        )

        await context.bot.send_message(chat_id=update.effective_chat.id, text=full_response)
        language_code = SpeechEngine.LANGUAGE_CODES.get(language, 'en')
        audio_filepath = await self.speech_engine.convert_text_to_speech(full_response, language_code=language_code)
        async with aiofiles.open(audio_filepath, 'rb') as audio_file:
            audio_content = await audio_file.read()
        await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio_content)
        os.remove(audio_filepath)

    async def send_text_and_voice_response(self, update: Update, context: CallbackContext, text: str) -> None:
        """
        Send a text message and its corresponding voice message to the user.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
            text (str): The text to send and convert to voice.
        """
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            audio_filepath = await self.speech_engine.convert_text_to_speech(text)

            async with aiofiles.open(audio_filepath, 'rb') as audio_file:
                audio_content = await audio_file.read()

            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio_content)

            os.remove(audio_filepath)
        except Exception as e:
            logger.error(f"Error in send_text_and_voice_response: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, an error occurred while generating the voice response."
            )

    async def _send_partial_voice_response(
            self,
            update: Update,
            context: CallbackContext,
            full_text: str,
            voice_text: str
    ) -> None:
        """
        Send a partial text response along with a voice message.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
            full_text (str): The full text to send.
            voice_text (str): The text to convert to voice.
        """
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=full_text)
            audio_filepath = await self.speech_engine.convert_text_to_speech(voice_text)

            async with aiofiles.open(audio_filepath, 'rb') as audio:
                voice_content = await audio.read()

            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=voice_content)

            os.remove(audio_filepath)
        except Exception as e:
            logger.error(f"Error in send_partial_voice_response: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, an error occurred while generating the voice response."
            )

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

    async def ping(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /ping command. Respond with the bot's latency.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "ping")
        start_time = time.time()
        message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Pinging...")
        end_time = time.time()
        latency_ms = round((end_time - start_time) * 1000, 2)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message.message_id,
            text=f"Pong! Latency is {latency_ms}ms"
        )

    async def start_speech_practice(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /start_speech_practice command. Initiate a speech practice session.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "start_speech_practice")
        welcome_message = (
            "Welcome to the speech practice session! "
            "Please send a voice message, and I'll respond with feedback."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message)
        context.user_data['in_speech_practice'] = True

    async def handle_voice(self, update: Update, context: CallbackContext) -> None:
        """
        Handle incoming voice messages. Convert speech to text and respond accordingly.

        Args:
            update (Update): Incoming update containing the voice message.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "voice")

        mp3_filepath = None
        response_audio_filepath = None

        try:
            async with self.speech_engine.download_voice_as_ogg(update.message.voice) as ogg_filepath:
                mp3_filepath = await self.speech_engine.convert_ogg_to_mp3(ogg_filepath)
                transcript_text = await self.speech_engine.convert_speech_to_text(mp3_filepath)

            if context.user_data.get('in_speech_practice', False):
                prompt = (
                    "You are an experienced English tutor helping a student improve their speaking skills. "
                    f"The student has just said: '{transcript_text}'. "
                    "Provide constructive feedback on their pronunciation, grammar, and vocabulary usage. "
                    "Encourage them to elaborate on their thoughts or ask a follow-up question to continue the "
                    "conversation."
                )
                response = await self.ai_engine.generate_response(prompt)
            else:
                response = await self.ai_engine.generate_response(transcript_text)

            response_audio_filepath = await self.speech_engine.convert_text_to_speech(response)

            await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
            async with aiofiles.open(response_audio_filepath, 'rb') as audio_file:
                voice_content = await audio_file.read()
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=voice_content)

        except Exception as e:
            logger.error(f"Error in handle_voice: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, I encountered an error while processing your voice message. Please try again."
            )
        finally:
            for filepath in [mp3_filepath, response_audio_filepath]:
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                        logger.debug(f"Removed temporary file: {filepath}")
                    except Exception as remove_err:
                        logger.error(f"Failed to remove file {filepath}: {remove_err}")

    async def meaning(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /meaning command. Provide the definition and usage example of a word.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "meaning")
        word = self._extract_command_text(update.message.text, "/meaning")

        if not word:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide a word to define. Usage: /meaning <word>"
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Generating definitions and sentence example for: {word}"
        )

        prompt = (
            f"Please provide the meaning/definition and a usage example for the word '{word}' "
            f"in the following format:\n"
            "Word: [insert word]\n"
            "Definition: [insert definition]\n"
            "Use-Case: [insert sentence example]"
        )
        response = await self.ai_engine.generate_response(prompt)
        await self.send_text_and_voice_response(update, context, response)

    async def email(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /email command. Compose an email based on user-provided information.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="email",
            prompt_template="Please write an email on the following information/context: {info}"
        )

    async def letter(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /letter command. Compose a letter based on user-provided information.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="letter",
            prompt_template="Please write a letter on the following information/context: {info}"
        )

    async def summarise(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /summarise command. Generate a summary of provided information.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="summarise",
            prompt_template="Please write a summary of the following information/paragraph: {info}"
        )

    async def essay(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /essay command. Generate an essay based on user-provided topic.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="essay",
            prompt_template=(
                "Please write me an essay on '{info}' in 4000 symbols. "
                "Use high-quality vocabulary and maintain simple language. "
                "Also, mention the approximate word count."
            )
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

    async def translate_text(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /translate command. Translate provided text to Ukrainian.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "translate")
        text_to_translate = self._extract_command_text(update.message.text, "/translate")
        if not text_to_translate:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide some text to translate. Usage: /translate <text>"
            )
            return

        target_language = self.get_target_language(context)
        translated_text = await self.ai_engine.translate_text(
            text_to_translate,
            target_language=target_language
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Original: {text_to_translate}\nTranslated to {target_language.capitalize()}: {translated_text}"
        )

    async def grammar_check(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /grammar_check command. Check and correct grammar in provided text.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "grammar_check")
        text_to_check = self._extract_command_text(update.message.text, "/grammar_check")

        if not text_to_check:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide some text to check. Usage: /grammar_check <your text>"
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Checking grammar..."
        )

        corrected_text = await self.ai_engine.grammar_check(text_to_check)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Original text:\n{text_to_check}\n\nCorrected text:\n{corrected_text}"
        )

    async def quiz(self, update: Update, context: CallbackContext) -> int:
        """
        Handle the /quiz command. Start a translation quiz session.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.

        Returns:
            int: The next state in the conversation.
        """
        self._log_command(update, "quiz")
        target_language = self.get_target_language(context)
        quiz_data = await self.ai_engine.generate_quiz_question()
        if not quiz_data:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Sorry, I couldn't generate a quiz question for {target_language.capitalize()} at the moment."
            )
            return ConversationHandler.END

    @staticmethod
    async def check_answer(update: Update, context: CallbackContext) -> int:
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

        # Clean up quiz data
        context.user_data.pop('quiz_data', None)
        return ConversationHandler.END

    @staticmethod
    def _extract_command_text(message_text: str, command: str) -> Optional[str]:
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

    async def _generate_ai_response(self, prompt: str) -> str:
        """
        Generate a response using the AI engine based on the provided prompt.

        Args:
            prompt (str): The prompt to send to the AI engine.

        Returns:
            str: The AI-generated response.
        """
        return await self.ai_engine.generate_response(prompt)

    @staticmethod
    def _log_command(update: Update, command: str) -> None:
        """
        Log the invocation of a command by a user.

        Args:
            update (Update): Incoming update.
            command (str): The command that was invoked.
        """
        username = update.effective_user.username or "Unknown User"
        logger.info(f"/{command} invoked by @{username}")

    async def restart_bot(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /restart command. Restart the bot application.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "restart")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Restarting...")

        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            logger.error(f"Error restarting bot: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Restart failed: {e}"
            )

    async def dev_info(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /dev command. Provide developer information.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "dev_info")
        developer_info = (
            "👨🏻‍💻 Developer Information:\n"
            "Name: Akshat Singh\n"
            "🇮🇳 Nationality\n"
            "🌐 Languages: English, Hindi\n"
            "🐙 GitHub: github.com/a3ro-dev/\n"
            "📬 Telegram: @a3roxyz"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=developer_info)

    async def _handle_ai_command(
            self,
            update: Update,
            context: CallbackContext,
            command: str,
            prompt_template: str
    ) -> None:
        """
        General handler for AI-based commands that require generating a response based on user input.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
            command (str): The command being handled.
            prompt_template (str): The template for the AI prompt.
        """
        self._log_command(update, command)
        user_input = self._extract_command_text(update.message.text, f"/{command}")

        if not user_input:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Please provide the necessary information for the /{command} command."
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Generating response for: {user_input}"
        )

        prompt = prompt_template.format(info=user_input)
        response = await self._generate_ai_response(prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    async def compose(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /compose command. Compose a text based on user-provided information.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="compose",
            prompt_template=(
                "Compose a {info} using high-quality English vocabulary with no grammatical errors. "
                "Make it sound original."
            )
        )

    async def rewrite(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /rewrite command. Rewrite provided text for better quality.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="rewrite",
            prompt_template=(
                "Rewrite the following text using high-quality English vocabulary with no grammatical errors. "
                "Make it sound original:\n\n{info}"
            )
        )

    async def ticket(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /ticket command. Create an issue ticket based on user input.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self._log_command(update, "ticket")
        ticket_info = self._extract_command_text(update.message.text, "/ticket")

        if not ticket_info:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide the issue details. Usage: /ticket <issue description>"
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Creating issue ticket for: {ticket_info}"
        )

        prompt = (
            "Explain the user's problem in clear technical language:\n\n"
            f"User Message: {ticket_info}"
        )
        ticket_description = self._generate_ai_response(prompt)

        try:
            await context.bot.send_message(
                chat_id=EnvSettings.ADMIN_ID,
                text=f"{ticket_description}\n\nIssue Raised by: @{update.effective_user.username}"
            )

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Issue sent to admin:\n{ticket_description}"
            )
        except Exception as e:
            logger.error(f"Error sending ticket to admin: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Failed to send issue to admin. Please try again later.\nError: {e}"
            )

    async def pronounce(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /pronounce command. Provide pronunciation guidance for provided text.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        await self._handle_ai_command(
            update,
            context,
            command="pronounce",
            prompt_template=(
                "Teach me how to pronounce {info}. Explain it in simple English in 2-3 lines."
            )
        )

    @staticmethod
    def _admin_only():
        """
        Decorator to restrict command usage to the admin only.

        Returns:
            function: The decorator function.
        """

        def decorator(callback):
            async def wrapper(update: Update, context: CallbackContext):
                if update.effective_user.id != EnvSettings.ADMIN_ID:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="You are not authorized to use this command."
                    )
                    return
                return await callback(update, context)

            return wrapper

        return decorator
