import logging.config
import os

import aiofiles
from telegram import Update
from telegram.ext import CallbackContext

from src.configs.log_config import LOGGING
from src.utils import helpers

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class VoiceHandlers:
    def __init__(self, ai_engine, speech_engine):
        self.ai_engine = ai_engine
        self.speech_engine = speech_engine
        self.log_command = helpers.log_command

    async def handle_voice(self, update: Update, context: CallbackContext) -> None:
        """
        Handle incoming voice messages. Convert speech to text and respond accordingly.

        Args:
            update (Update): Incoming update containing the voice message.
            context (CallbackContext): Contextual information.
        """
        self.log_command(update, "voice")

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
