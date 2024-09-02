import logging.config
import os
import time
import random
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
import psutil
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, Application, MessageHandler, filters, ConversationHandler
from telegram.request import HTTPXRequest
from src.audio.speech import SpeechEngine
from src.configs.log_config import LOGGING
from src.configs.config import EnvSettings, TelegramData
from src.open_ai.openai_init import OpenAIEngine

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        request = HTTPXRequest(connection_pool_size=8, connect_timeout=180, read_timeout=180)
        self.ai = OpenAIEngine()
        self.speech_engine = SpeechEngine()
        self.application = self._create_application_with_retry(request)
        self.bot = self.application.bot

        self._setup_handlers()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _create_application_with_retry(self, request):
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

                audio_filepath = self.speech_engine.convert_text_to_speech(quiz_data['english_sentence'])

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

    async def _log_system_info(self) -> None:
        if self.bot.get_me():
            logging.info(f"Logged in as {self.bot.get_me()}")
        else:
            logging.error("Failed to log in.")

        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage('/').percent
        logging.info(
            f"CPU: {cpu_percent}% {'🔥' if cpu_percent > 80 else ''} | "
            f"Memory: {memory_percent}% {'☁' if memory_percent > 80 else ''} | "
            f"Disk: {disk_percent}% {'💾' if disk_percent > 80 else ''}"
        )

    async def start(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "start")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Hello there! I am English-tutor bot, designed to help you improve your vocabulary"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="To get started, just type /help and I'll show you the way. Let's expand our vocabulary together 😊"
        )

    async def help(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "help")
        help_text = """
        👋 Welcome to @erocabulary_bot Here are some of my available commands:
        ⭐ /start  [sends a greeting message to get you started.] 
        📚 /send_vocab  [improves your vocabulary by sending 
        a random English word with its definition and use case.] 
        📝 /compose <topic> [composes a poem, story, 
        or ideas.] 🗣️ /pronounce <word> [learn to pronounce a word.] 
        🏻 /rewrite <content> [rephrases and rewrites 
        the given content with correct English.] 
        📖 /meaning <word/phrase>  [gets you the definition and sentence 
        example of the requested word/phrase.] 
        📝 /essay <topic>  [provides you with an essay of 200 words on the 
        given topic.] 
        📧 /email <email formal or informal | content | information | context>  [writes an email on the 
        given information.] ✉ /letter <letter formal or informal | topic | information | context> [writes a letter on 
        the given information.] 
        🔤 /summarise <paragraph> [produces a summmary on the given paragraph | information | 
        topic] 
        🌐 /ping  [the round-trip latency in milliseconds between this bot and the Telegram servers.] ℹ /dev [
        information regarding the desveloper of this bot.] 
        📝 /grammar_check <text> [checks and corrects the grammar 
        of the provided text.] 
        🔄 /translate <text> [translates the provided text to Ukrainian.] 🎟️ /ticket <issue>
        🎯 /quiz [start a quiz to test your English to Ukrainian translation skills]
        📅 /subscribe_quiz [subscribe to hourly quizzes]
        🚫 /unsubscribe_quiz [unsubscribe from hourly quizzes]

        *DEBUG*
        📥 /stats  [gets you some statistics about the bot.]
        ❌ /logs [retrieves the log file for debugging.]
        🔁 /restart [restarts the bot (admin only)]
        🎫/tick [sends your message to the developers of this bot]

        I'm your one-stop-shop for all things English related, designed to help you enhance your language skills with 
        ease and convenience. Start improving your English language proficiency today!"""
        await context.bot.send_message(chat_id=update.effective_chat.id, text=help_text)

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

    async def send_text_and_voice_response(self, update: Update, context: CallbackContext, text: str) -> None:
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
            audio_filepath = self.speech_engine.convert_text_to_speech(text)
            with open(audio_filepath, 'rb') as audio:
                await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio)
            os.remove(audio_filepath)
        except Exception as e:
            logging.error(f"Error in send_text_and_voice_response: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Sorry, an error occurred while generating the voice response."
            )

    async def handle_voice(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "voice")

        ogg_filepath = await self.speech_engine.download_voice_as_ogg(update.message.voice)
        mp3_filepath = self.speech_engine.convert_ogg_to_mp3(ogg_filepath)
        transcript_text = self.speech_engine.convert_speech_to_text(mp3_filepath)
        answer = self.speech_engine.generate_response(transcript_text)
        response_audio_filepath = self.speech_engine.convert_text_to_speech(answer)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=answer)
        with open(response_audio_filepath, 'rb') as audio:
            await context.bot.send_voice(chat_id=update.effective_chat.id, voice=audio)

        os.remove(ogg_filepath)
        os.remove(mp3_filepath)
        os.remove(response_audio_filepath)

    async def send_vocab(self, update: Update, context: CallbackContext) -> None:
        self._log_command(update, "send_vocab")
        random_seed = random.randint(1, 1000000)
        prompt = f"""
        Please provide a brief English word or phrase from spoken English, also provide an Ukrainian translated version.
        Format your response as follows:
            Word: [insert word or phrase]
            Definition: [insert brief definition]
            Use-Case: [insert brief sentence example]
            Слово: [вставити слово або словосполучення]
            Визначення: [вставити коротке визначення]
            Use-Case: [вставити короткий приклад речення].
            Keep the entire response under 50 words.
            Seed: {random_seed}  # Include the random seed in the prompt
        """
        response = self._generate_ai_response(prompt)

        await self.send_text_and_voice_response(update, context, response)

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
        print("Quiz method called")
        try:
            if update.effective_user:
                self._log_command(update, "quiz")
            logging.info("Generating quiz question...")

            quiz_data = self.ai.generate_quiz_question()
            if not quiz_data:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Sorry, I couldn't generate a quiz question at the moment. Please try again later."
                )
                return ConversationHandler.END

            audio_filepath = self.speech_engine.convert_text_to_speech(quiz_data['english_sentence'])

            with open(audio_filepath, 'rb') as audio:
                await context.bot.send_voice(
                    chat_id=update.effective_chat.id,
                    voice=audio,
                    caption="Listen to the sentence and provide the correct Ukrainian translation."
                )

            os.remove(audio_filepath)

            context.user_data['quiz_data'] = quiz_data
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please type your Ukrainian translation:"
            )

            return TelegramData.ANSWER
        except Exception as e:
            logging.error(f"Error in quiz method: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="An error occurred while starting the quiz. Please try again later."
            )
            return ConversationHandler.END

    @staticmethod
    async def check_answer(update: Update, context: CallbackContext) -> int:
        print("Check answer method called")
        logging.info("Check answer method called")
        user_answer = update.message.text
        chat_id = update.effective_chat.id

        if 'scheduled_quizzes' in context.bot_data and chat_id in context.bot_data['scheduled_quizzes']:
            quiz_data = context.bot_data['scheduled_quizzes'].pop(chat_id)
        else:
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
            text=f"{result_text}\n\nEnglish sentence: "
                 f"{result_text}\n\nEnglish sentence: "
                 f"{quiz_data['english_sentence']}"
        )

        context.user_data.pop('quiz_data', None)
        return ConversationHandler.END

    @staticmethod
    def _extract_command_text(message_text: str, command: str) -> Optional[str]:
        text = message_text.replace(command, "").strip()
        return text if text else None

    def _generate_ai_response(self, prompt: str) -> str:
        self.ai.get_prompt(prompt)
        return self.ai.generate_response()

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

    def restart_bot(self, update: Update, context: CallbackContext):
        self._log_command(update, "restart")
        context.bot.send_message(chat_id=update.effective_chat.id, text="Restarting...")
        try:
            import os
            import sys
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception as e:
            logging.error(f"Error restarting bot: {e}")
            context.bot.send_message(chat_id=update.effective_chat.id, text=f"Restart failed: {e}")

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
