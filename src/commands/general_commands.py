import logging.config
import os

import aiofiles
from telegram import Update
from telegram.ext import CallbackContext

from src.audio.speech_engine import SpeechEngine
from src.configs.log_config import LOGGING
from src.configs.settings import EnvSettings
from src.utils import helpers

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class GeneralCommands:
    def __init__(self, ai_engine, speech_engine, word_database):
        self.ai_engine = ai_engine
        self.speech_engine = speech_engine
        self.word_database = word_database
        self.extract_command_text = helpers.extract_command_text
        self.log_command = helpers.log_command
        self.get_target_language = helpers.get_target_language

    async def set_language(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /set_language command to set the user's preferred target language.
        """
        self.log_command(update, "set_language")
        language = self.extract_command_text(update.message.text, "/set_language")
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

    async def send_vocab(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /send_vocab command. Send a random word with its definition and usage examples.
        """
        self.log_command(update, "send_vocab")
        language = self.get_target_language(context)
        word_db = self.word_database.get(language)

        if not word_db:
            logger.warning(f"No word database found for language: {language}")
            await update.message.reply_text(f"Sorry, no word database found for {language}.")
            return

        word = word_db.get_random_word()

        if not word:
            logger.warning(f"No words available in the {language} database.")
            await update.message.reply_text(f"Sorry, no words available in the {language} database.")
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

    async def start_speech_practice(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /start_speech_practice command. Initiate a speech practice session.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "start_speech_practice")
        welcome_message = (
            "Welcome to the speech practice session! "
            "Please send a voice message, and I'll respond with feedback."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message)
        context.user_data['in_speech_practice'] = True

    async def meaning(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /meaning command. Provide the definition and usage example of a word.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "meaning")
        word = self.extract_command_text(update.message.text, "/meaning")

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
            f"Please provide the meaning/definition and a usage example for the German or English word '{word}' "
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
            prompt_template="Please write a letter on the following information/context in 50 words: {info}"
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

    async def translate_text(self, update: Update, context: CallbackContext) -> None:
        """
        Handle the /translate command. Translate provided text to Ukrainian.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "translate")
        text_to_translate = self.extract_command_text(update.message.text, "/translate")
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
        self.log_command(update, "grammar_check")
        text_to_check = self.extract_command_text(update.message.text, "/grammar_check")

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

    async def _generate_ai_response(self, prompt: str) -> str:
        """
        Generate a response using the AI engine based on the provided prompt.

        Args:
            prompt (str): The prompt to send to the AI engine.

        Returns:
            str: The AI-generated response.
        """
        return await self.ai_engine.generate_response(prompt)

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
        self.log_command(update, command)
        user_input = self.extract_command_text(update.message.text, f"/{command}")

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
                "Compose a {info} using high-quality English or German vocabulary with no grammatical errors. "
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
                "Rewrite the following text using high-quality English or German vocabulary with no grammatical errors."
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
        self.log_command(update, "ticket")
        ticket_info = self.extract_command_text(update.message.text, "/ticket")

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
        Handle the /pronounce command. Provide pronunciation guidance for provided text and send an audio file.

        Args:
            update (Update): Incoming update.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "pronounce")
        text_to_pronounce = self.extract_command_text(update.message.text, "/pronounce")

        if not text_to_pronounce:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Please provide a word or phrase to pronounce. Usage: /pronounce <word or phrase>"
            )
            return

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Generating pronunciation guidance for: {text_to_pronounce}"
        )

        prompt = f"Teach me how to pronounce '{text_to_pronounce}'. Explain it in simple English in 2-3 lines."
        pronunciation_guidance = await self._generate_ai_response(prompt)

        full_response = f"Pronunciation guidance for '{text_to_pronounce}':\n\n{pronunciation_guidance}"

        await self.send_text_and_voice_response(update, context, full_response)

        audio_filepath = await self.speech_engine.convert_text_to_speech(text_to_pronounce)

        async with aiofiles.open(audio_filepath, 'rb') as audio_file:
            audio_content = await audio_file.read()

        await context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=audio_content,
            caption=f"Pronunciation of '{text_to_pronounce}'"
        )

        os.remove(audio_filepath)
