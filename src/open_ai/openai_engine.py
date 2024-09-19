import logging.config
import random
from typing import Dict, List, Optional

import openai
from openai import OpenAIError

from src.configs.log_config import LOGGING
from src.configs.settings import EnvSettings, OpenaiSettings

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class OpenAIEngine:
    """Engine to interact with OpenAI API."""

    def __init__(self):
        self.api_key = EnvSettings.OPENAI_API_KEY
        openai.api_key = self.api_key
        self.model = OpenaiSettings.OPENAI_MODEL

    @staticmethod
    def _process_response(response) -> str:
        """Process the OpenAI response and extract the content."""
        try:
            return response.choices[0].message.content
        except (KeyError, IndexError) as e:
            logger.error(f"Error processing response: {e}")
            return "Sorry, I couldn't process the response."

    async def _create_completion(self, model: str, messages: List[Dict], **kwargs) -> str:
        """Create a completion using the specified model and messages."""
        try:
            response = openai.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return self._process_response(response)
        except OpenAIError as e:
            logger.error(f"OpenAI API error: {e}")
            return "Sorry, an error occurred while processing your request."
        except Exception as e:
            logger.exception(f"Unexpected error in _create_completion: {e}")
            return "Sorry, an unexpected error occurred."

    async def translate_text(self, text: str, target_language: str = "english") -> str:
        """Translate text to the target language."""
        messages = [
            {
                "role": "user",
                "content": f"Translate the following text to {target_language}: '{text}'."
            }
        ]
        return await self._create_completion(OpenaiSettings.OPENAI_MODEL, messages)

    async def generate_response(self, prompt: str) -> str:
        """Generate a response based on the given prompt."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant that specializes in English language tutoring."},
            {"role": "user", "content": prompt}
        ]
        return await self._create_completion(OpenaiSettings.OPENAI_MODEL, messages, temperature=0.4)

    async def grammar_check(self, text: str) -> str:
        """Check the grammar of the given text."""
        messages = [
            {"role": "system", "content": "You are an expert English grammar checker. Correct the following text and "
                                          "return the corrected version. If there are no errors, return 'No "
                                          "corrections needed.' followed by the original text."},
            {"role": "user", "content": text}
        ]
        return await self._create_completion(OpenaiSettings.OPENAI_MODEL, messages, temperature=0.3)

    async def generate_quiz_question(self) -> Optional[Dict]:
        """Generate a quiz question with multiple choice options."""
        messages = [
            {"role": "system", "content": "Generate a short English sentence (5-10 words) and provide its "
                                          "translation. Also, provide three incorrect translations."},
            {"role": "user", "content": "Generate a quiz question."}
        ]
        content = await self._create_completion(OpenaiSettings.OPENAI_MODEL, messages, temperature=0.5)
        lines = content.split('\n')

        if len(lines) < 5:
            logger.error("Incomplete quiz question generated.")
            return None

        english_sentence = lines[0].replace('English: ', '').strip()
        correct_translation = lines[1].replace('Correct Translation: ', '').strip()
        incorrect_translations = [
            line.replace('Incorrect Translation: ', '').strip()
            for line in lines[2:5]
        ]

        all_options = [correct_translation] + incorrect_translations
        random.shuffle(all_options)

        return {
            'english_sentence': english_sentence,
            'correct_translation': correct_translation,
            'options': all_options
        }

    async def summarize_text(self, text: str) -> str:
        """Summarize the given text."""
        messages = [
            {"role": "system", "content": "Summarize the following text concisely:"},
            {"role": "user", "content": text}
        ]
        return await self._create_completion(OpenaiSettings.OPENAI_MODEL, messages)
