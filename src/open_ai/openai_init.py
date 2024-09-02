import logging.config
import random

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.configs.log_config import LOGGING
from src.configs.config import EnvSettings

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class OpenAIEngine:
    def __init__(self):
        self.prompt = ""
        self.client = OpenAI(api_key=EnvSettings.OPENAI_API_KEY)

    def get_prompt(self, prompt):
        self.prompt = prompt

    def translate_text(self, text, source_language="en", target_language="uk"):
        try:
            translation = self.client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {
                        "role": "user",
                        "content": f"Translate '{text}' from {source_language} to {target_language}."
                    }
                ]
            )
            return translation.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error during translation: {e}")
            return "Sorry, an error occurred while translating the text."

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_response(self):
        try:
            response = self.client.chat.completions.create(
                model='gpt-4o',
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that specializes in English language "
                                                  "tutoring."},
                    {"role": "user", "content": self.prompt}
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(e)
            return "Sorry, an error occurred while generating the response."

    def grammar_check(self, text: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model='gpt-4o-2024-08-06',
                messages=[
                    {"role": "system", "content": "You are an expert English grammar checker. Correct the following "
                                                  "text and return the corrected version. If there are no errors, "
                                                  "return 'No corrections needed.' followed by the original text."},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error in grammar_check: {e}")
            return "Sorry, an error occurred while checking the grammar."

    def generate_quiz_question(self) -> dict:
        try:
            response = self.client.chat.completions.create(
                model='gpt-4o-2024-08-06',
                messages=[
                    {"role": "system",
                     "content": "Generate a short English sentence (5-10 words) and provide its Ukrainian "
                                "translation. Also, provide three incorrect Ukrainian translations."},
                    {"role": "user", "content": "Generate a quiz question."}
                ],
                temperature=0.5,
            )
            content = response.choices[0].message.content.strip()
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
        except Exception as e:
            logging.error(f"Error in generate_quiz_question: {e}")
            return {
                'english_sentence': 'Error',
                'correct_translation': 'Error',
                'options': ['Error']
            }
