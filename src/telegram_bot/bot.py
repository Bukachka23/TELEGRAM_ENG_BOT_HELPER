import aiofiles
import logging.config
import os
import time
from typing import Optional, NoReturn
from tenacity import retry, stop_after_attempt, wait_exponential
import psutil
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, Application, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest
from src.audio.speech import SpeechEngine
from src.configs.log_config import LOGGING
from src.configs.config import EnvSettings, TelegramData
from src.database.database_words import WordDatabase
from src.open_ai.openai_init import OpenAIEngine

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        self.ai = OpenAIEngine()
        self.speech_engine = SpeechEngine()
        self.application = self._create_application_with_retry()
        self.bot = self.application.bot
        self.word_db = WordDatabase()

        self._setup_handlers()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _create_application_with_retry(self):
        request = HTTPXRequest(connection_pool_size=8, connect_timeout=180, read_timeout=180)
        return Application.builder().token(EnvSettings.TELEGRAM_BOT_TOKEN).request(request).build()

    def _setup_handlers(self) -> None:
        command_handlers = [
            ('start', self.start),
            ('help', self.help),
            ('send_vocab', self.send_vocab),
            ('meaning', self.meaning),
            ('email', self.email),
            ('essay', self.essay),
            ('ping', self.ping),
            ('stats', self.stats),
            ('restart', self.restart_bot),
            ('dev', self.dev_info),
            ('letter', self.letter),
            ('summarise', self.summarise),
            ('compose', self.compose),
            ('rewrite', self.rewrite),
            ('ticket', self.ticket),
            ('pronounce', self.pronounce),
            ('translate', self.translate_text),
            ('grammar_check', self.grammar_check),
            ('quiz', self.quiz),
            ('subscribe_quiz', self.subscribe_quiz),
            ('unsubscribe_quiz', self.unsubscribe_quiz),
        ]

        for command, callback in command_handlers:
            self.application.add_handler(CommandHandler(command, callback))

        self.application.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_answer))

        quiz_handler = ConversationHandler(
            entry_points=[CommandHandler('quiz', self.quiz)],
            states={
                TelegramData.ANSWER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.check_answer)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel_quiz)],
            name="quiz_conversation",
            persistent=False,
        )
        self.application.add_handler(quiz_handler)

    async def _log_system_info(self) -> None:
        bot_info = self.bot.get_me()
        if bot_info:
            logger.info(f"Logged in as {bot_info.username}")
        else:
            logger.error("Failed to log in.")

        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        logger.info(
            f"CPU: {cpu_percent}% {'🔥' if cpu_percent > 80 else ''} | "
            f"Memory: {memory_percent}% {'☁' if memory_percent > 80 else ''} | "
            f"Disk: {disk_percent}% {'💾' if disk_percent > 80 else ''}"
        )

    async def start(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "start")
        welcome_message = """
        Hello! I'm an English-tutor bot designed to help you improve your vocabulary.
        To get started, type /help for available commands.
        Let's expand our vocabulary together! 😊
        """
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message)

    async def help(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "help")
        help_text = """
        Available commands:
        /start - Greeting message
        /help - Show this help message
        /send_vocab - Improve vocabulary with random words
        /meaning <word> - Get definition and usage example
        /email <topic> - Compose an email
        /essay <topic> - Generate an essay
        /ping - Check bot latency
        /stats - Show system statistics
        /translate <text> - Translate to Ukrainian
        /grammar_check <text> - Check grammar
        /quiz - Start a translation quiz
        /subscribe_quiz - Subscribe to hourly quizzes
        /unsubscribe_quiz - Unsubscribe from hourly quizzes
        """
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

    async def send_vocab(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "send_vocab")
        word = self.word_db.get_random_word()

        if not word:
            logger.warning("No word found in database")
            await update.message.reply_text("Sorry, no word found in the database.")
            return

        prompts = [
            f"Define '{word}' in one sentence:",
            f"Generate a sentence using '{word}':",
            f"Define '{word}' in Ukrainian in one sentence:",
            f"Generate a Ukrainian sentence using '{word}':"
        ]

        responses = [self.ai.generate_response(prompt) for prompt in prompts]

        full_response = f"""
        Word: {word}
        Definition: {responses[0]}
        Example sentence: {responses[1]}

        Слово: {word}
        Визначення: {responses[2]}
        Приклад речення: {responses[3]}
        """

        voice_response = f"""
        Word: {word}
        Definition: {responses[0]}
        Example sentence: {responses[1]}
        """

        await self.send_partial_voice_response(update, context, full_response, voice_response)

    async def send_text_and_voice_response(self, update: Update, context: CallbackContext, text: str) -> NoReturn:
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

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _create_application_with_retry(self):
        return Application.builder().token(EnvSettings.TELEGRAM_BOT_TOKEN).build()

    @staticmethod
    async def cancel_quiz(update: Update, context: CallbackContext) -> int:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Quiz cancelled. You can start a new quiz anytime with /quiz."
        )
        return ConversationHandler.END

    async def scheduled_quiz(self, context: CallbackContext) -> None:
        start_time = time.time()
        logging.info("Starting scheduled quiz")
        chat_ids = context.bot_data.get('subscribed_users', [])
        for chat_id in chat_ids:
            try:
                logging.info(f"Sending scheduled quiz to {chat_id}")
                quiz_data = self.ai.generate_quiz_question()
                if not quiz_data:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="Sorry, I couldn't generate a quiz question at the moment. Please try again later."
                    )
                    continue

                audio_filepath = await self.speech_engine.convert_text_to_speech(quiz_data['english_sentence'])

                with open(audio_filepath, 'rb') as audio:
                    await context.bot.send_voice(
                        chat_id=chat_id,
                        voice=audio,
                        caption="Listen to the sentence and provide the correct Ukrainian translation."
                    )

                os.remove(audio_filepath)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Please type your Ukrainian translation:"
                )

                if 'scheduled_quizzes' not in context.bot_data:
                    context.bot_data['scheduled_quizzes'] = {}
                context.bot_data['scheduled_quizzes'][chat_id] = quiz_data

            except Exception as e:
                logging.error(f"Error sending scheduled quiz to {chat_id}: {e}")

            end_time = time.time()
            logging.info(f"Scheduled quiz completed in {end_time - start_time} seconds")

    @staticmethod
    async def subscribe_quiz(update: Update, context: CallbackContext) -> None:
        logging.info("Subscribe quiz method called")
        chat_id = update.effective_chat.id
        if 'subscribed_users' not in context.bot_data:
            context.bot_data['subscribed_users'] = []

        if chat_id not in context.bot_data['subscribed_users']:
            context.bot_data['subscribed_users'].append(chat_id)
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
        logging.info("Unsubscribe quiz method called")
        chat_id = update.effective_chat.id
        if 'subscribed_users' in context.bot_data and chat_id in context.bot_data['subscribed_users']:
            context.bot_data['subscribed_users'].remove(chat_id)
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
        self._log_command(update, "ping")
        start_time = time.time()
        message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Pinging..")
        end_time = time.time()
        latency = round((end_time - start_time) * 1000, 2)
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message.message_id,
            text=f"Pong! Latency is {latency}ms"
        )

    async def handle_voice(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "voice")

        async with self.speech_engine.download_voice_as_ogg(update.message.voice) as ogg_filepath:
            mp3_filepath = await self.speech_engine.convert_ogg_to_mp3(ogg_filepath)
            transcript_text = await self.speech_engine.convert_speech_to_text(mp3_filepath)
            answer = await self.speech_engine.generate_response(transcript_text)
            response_audio_filepath = await self.speech_engine.convert_text_to_speech(answer)

            await context.bot.send_message(chat_id=update.effective_chat.id, text=answer)
            with open(response_audio_filepath, 'rb') as audio:
                await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio)

            os.remove(mp3_filepath)
            os.remove(response_audio_filepath)

    async def send_partial_voice_response(self, update: Update, context: CallbackContext, full_text: str,
                                          voice_text: str) -> None:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=full_text)
            audio_filepath = await self.speech_engine.convert_text_to_speech(voice_text)

            async with aiofiles.open(audio_filepath, 'rb') as audio:
                await context.bot.send_voice(chat_id=update.effective_chat.id, voice=await audio.read())

            os.remove(audio_filepath)
        except Exception as e:
            logger.error(f"Error in send_partial_voice_response: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, an error occurred while generating the voice response."
            )

    async def meaning(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "meaning")
        word = update.message.text.replace('/meaning ', '')
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Generating definitions and sentence example for: {word}"
        )
        prompt = f"""
        Please tell me the the meaning/definition, use case(sentence example) of {word} in this format
        Word: [insert word or phrase]
        Definition: [insert definition]
        Use-Case: [insert sentence example]
        """
        response = self._generate_ai_response(prompt)
        await self.send_text_and_voice_response(update, context, response)

    async def email(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(update, context, "email",
                                      "Please write an email on the following information/context {info}")

    async def letter(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(update, context, "letter",
                                      "Please write a letter on the following information/context {info}")

    async def summarise(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(update, context, "summarise",
                                      "Please write a summary on the following "
                                      "information/paragraph: {info}")

    async def essay(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(update, context, "essay",
                                      "Please write me an essay on {info} in 4000 symbols, "
                                      "also please use high quality vocabulary and keep "
                                      "it in simple language, also do mention approx. word count")

    @staticmethod
    async def stats(update: Update, context: CallbackContext) -> None:
        try:
            logging.info("/stats invoked!")
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage('/').percent
            message = (f"CPU: {cpu_percent}% {'🔥' if cpu_percent > 80 else ''} \nMemory: {memory_percent}% "
                       f"{'☁' if memory_percent > 80 else ''} \nDisk: "
                       f"{disk_percent}% {'💾' if disk_percent > 80 else ''}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
        except Exception as e:
            logging.error(e)
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"Exception occured while generating stats.\nErrorMessage:\n{e}")

    async def translate_text(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "translate")
        text = update.message.text.replace('/translate ', '').strip()

        if not text:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text="Please provide some text to translate.")
            return

        translated_text = self.ai.translate_text(text)

        logging.info(f"Translation result: {translated_text}")

        try:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"Original: {text}\nTranslated: {translated_text}")
        except Exception as e:
            logging.error(f"Error sending translation result: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"Sorry, an error occurred while sending the translation "
                                                f"result.\nError: {str(e)}")

    async def grammar_check(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "grammar_check")
        text = self._extract_command_text(update.message.text, "/grammar_check")

        if not text:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide some text to check. Usage: /grammar_check <your text>"
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Checking grammar..."
        )
        corrected_text = self.ai.grammar_check(text)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Original text:\n{text}\n\nCorrected text:\n{corrected_text}"
        )

    async def quiz(self, update: Update, context: CallbackContext) -> int:
        self._log_command(update, "quiz")
        logging.info("Generating quiz question...")

        quiz_data = self.ai.generate_quiz_question()
        if not quiz_data:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, I couldn't generate a quiz question at the moment. Please try again later."
            )
            return ConversationHandler.END

        audio_filepath = await self.speech_engine.convert_text_to_speech(quiz_data['english_sentence'])

        async with aiofiles.open(audio_filepath, 'rb') as audio:
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=await audio.read(),
                caption="Listen to the sentence and provide the correct Ukrainian translation."
            )

        os.remove(audio_filepath)

        context.user_data['quiz_data'] = quiz_data
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Please type your Ukrainian translation:"
        )

        return TelegramData.ANSWER

    @staticmethod
    async def check_answer(update: Update, context: CallbackContext) -> int:
        user_answer = update.message.text
        chat_id = update.effective_chat.id

        quiz_data = context.user_data.get('quiz_data')

        if not quiz_data:
            await context.bot.send_message(
                chat_id=chat_id,
                text="Sorry, I couldn't retrieve the quiz data. Please start a new quiz."
            )
            return ConversationHandler.END

        if user_answer.lower() == quiz_data['correct_translation'].lower():
            result_text = "🎉 Correct! Well done!"
        else:
            result_text = f"❌ Sorry, that's not correct. The right answer is:\n\n{quiz_data['correct_translation']}"

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{result_text}\n\nEnglish sentence: {quiz_data['english_sentence']}"
        )

        context.user_data.pop('quiz_data', None)
        return ConversationHandler.END

    @staticmethod
    def _extract_command_text(message_text: str, command: str) -> Optional[str]:
        text = message_text.replace(command, "").strip()
        return text if text else None

    def _generate_ai_response(self, prompt: str) -> str:
        return self.ai.generate_response(prompt)

    @staticmethod
    def _log_command(update: Update, command: str):
        logging.info(f"/{command} invoked by {update.effective_user.username}")

    def run(self):
        self.application.start_polling()

    @staticmethod
    def _admin_only():
        def wrapper(update: Update, context: CallbackContext):
            if update.effective_user.id != EnvSettings.ADMIN_ID:
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="You are not authorized to use this command."
                )
                return
            return context

        return wrapper

    async def restart_bot(self, update: Update, context: CallbackContext):
        self._log_command(update, "restart")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Restarting...")
        try:
            import os
            import sys
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            logging.error(f"Error restarting bot: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Restart failed: {e}")

    async def dev_info(self, update: Update, context: CallbackContext):
        self._log_command(update, "dev_info")
        dev_info = """
        👨🏻‍💻 Developer Information:
        Name: Akshat Singh
        🇮🇳 Nationality
        🌐 Languages: English, Hindi
        🐙 Github: github.com/a3ro-dev/
        📬 Telegram: @a3roxyz
        """
        await context.bot.send_message(chat_id=update.effective_chat.id, text=dev_info)

    async def _handle_ai_command(self, update: Update, context: CallbackContext, command: str, prompt_template: str):
        self._log_command(update, command)
        text = update.message.text
        info = text.replace(f"/{command}", "").strip()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Generating response for: {info}")
        prompt = prompt_template.format(info=info)
        response = self._generate_ai_response(prompt)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

    async def compose(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(
            update, context, "compose",
            "Compose a {info} in high-quality English vocabulary with no grammatical errors. Make it sound original."
        )

    async def rewrite(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(
            update, context, "rewrite",
            "Rewrite this text in high-quality English vocabulary with no grammatical errors. Make it sound "
            "original:\n\n{info}"
        )

    async def ticket(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "ticket")
        text = update.message.text
        ticket_info = text.replace("/ticket", "").strip()
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=f"Creating issue check for: {ticket_info}")
        prompt = f"Explain the user's problem in clear technical language:\n\nUser Message: {ticket_info}"
        ticket = self._generate_ai_response(prompt)
        await context.bot.send_message(
            chat_id=EnvSettings.ADMIN_ID,
            text=f"{ticket}\n\nIssue Raised by: {update.effective_user.username}"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Issue Sent to admin:\n{ticket}")

    async def pronounce(self, update: Update, context: CallbackContext) -> None:
        await self._handle_ai_command(
            update, context, "pronounce",
            "Teach me how to pronounce {info}. Explain it in simple English in 2-3 lines."
        )

    async def initialize(self) -> None:
        await self._log_system_info()
