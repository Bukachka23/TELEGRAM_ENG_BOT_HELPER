import logging.config
import random
from typing import Dict, List

from openai import OpenAI

from src.configs.log_config import LOGGING
from src.configs.config import EnvSettings, OpenaiSettings

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class OpenAIEngine:
    def __init__(self):
        self.client = OpenAI(api_key=EnvSettings.OPENAI_API_KEY)

    @staticmethod
    def _process_response(response) -> str:
        """Process the OpenAI response and extract the content."""
        return response.choices[0].message.content.strip()

    def _create_completion(self, model: str, messages: List[Dict], **kwargs) -> str:
        """Create a completion using the specified model and messages."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs
            )
            return self._process_response(response)
        except Exception as e:
            logger.error(f"Error in create_completion: {e}")
            return f"Sorry, an error occurred: {str(e)}"

    def translate_text(self, text: str, source_language: str = "en", target_language: str = "uk") -> str:
        """Translate text from source language to target language."""
        messages = [
            {
                "role": "user",
                "content": f"Translate '{text}' from {source_language} to {target_language}."
            }
        ]
        return self._create_completion(OpenaiSettings.OPENAI_MODEL, messages)

    def generate_response(self, prompt: str) -> str:
        """Generate a response based on the given prompt."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant that specializes in English language tutoring."},
            {"role": "user", "content": prompt}
        ]
        return self._create_completion(OpenaiSettings.OPENAI_MODEL, messages, temperature=0.4)

    def grammar_check(self, text: str) -> str:
        """Check the grammar of the given text."""
        messages = [
            {"role": "system", "content": "You are an expert English grammar checker. Correct the following text and "
                                          "return the corrected version. If there are no errors, return 'No "
                                          "corrections needed.' followed by the original text."},
            {"role": "user", "content": text}
        ]
        return self._create_completion(OpenaiSettings.OPENAI_MODEL, messages, temperature=0.3)

    def generate_quiz_question(self) -> Dict:
        """Generate a quiz question with multiple choice options."""
        messages = [
            {"role": "system", "content": "Generate a short English sentence (5-10 words) and provide its Ukrainian "
                                          "translation. Also, provide three incorrect Ukrainian translations."},
            {"role": "user", "content": "Generate a quiz question."}
        ]
        content = self._create_completion(OpenaiSettings.OPENAI_MODEL, messages, temperature=0.5)
        lines = content.split('\n')

        english_sentence = lines[0].replace('English: ', '')
        correct_translation = lines[1].replace('Correct Ukrainian: ', '')
        incorrect_translations = [line.replace('Incorrect Ukrainian: ', '') for line in lines[2:5]]

        all_options = [correct_translation] + incorrect_translations
        random.shuffle(all_options)

        return {
            'english_sentence': english_sentence,
            'correct_translation': correct_translation,
            'options': all_options
        }

    def summarize_text(self, text: str) -> str:
        """Summarize the given text."""
        messages = [
            {"role": "system", "content": "Summarize the following text concisely:"},
            {"role": "user", "content": text}
        ]
        return self._create_completion(OpenaiSettings.OPENAI_MODEL, messages)
