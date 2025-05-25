"""Configuration management for Anki Bot."""

from pydantic_settings import BaseSettings
from pydantic import Field
import logging


class Settings(BaseSettings):
    """Application settings with validation."""

    # Telegram
    telegram_bot_token: str = Field(..., env='TELEGRAM_BOT_TOKEN')

    # Ollama
    ollama_url: str = Field('http://localhost:11434/api/generate', env='OLLAMA_URL')
    ollama_model: str = Field('gemma2:9b', env='OLLAMA_MODEL')

    # Anki
    anki_url: str = Field('http://localhost:8765', env='ANKI_URL')
    anki_deck_name: str = Field('Default', env='ANKI_DECK_NAME')
    anki_model_name: str = Field('Basic', env='ANKI_MODEL_NAME')

    # Bot behavior
    max_generation_attempts: int = Field(4, env='MAX_GENERATION_ATTEMPTS')
    generation_timeout: int = Field(60, env='GENERATION_TIMEOUT')
    sync_timeout: int = Field(30, env='SYNC_TIMEOUT')
    spell_check_timeout: int = Field(20, env='SPELL_CHECK_TIMEOUT')

    # Logging
    log_level: str = Field('INFO', env='LOG_LEVEL')

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


# Create global settings instance
settings = Settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Example prompts for better card generation
FEW_SHOT_EXAMPLES = """
Example 1 for word "received":
TRANSLATION: verb — отримав/отримала, past participle — отриманий
PART_OF_SPEECH: Verb (дієслово)
PRONUNCIATION: /rɪˈsiːvd/ (BrE), /rɪˈsiːvd/ (AmE)
EXPLANATION_NOUN: N/A
EXPLANATION_VERB: Past tense of receive; to have gotten or obtained something (отримав; одержав щось)
EXAMPLE_NOUN: N/A
EXAMPLE_VERB: I received your letter yesterday. (Я отримав твого листа вчора.)

Example 2 for word "run":
TRANSLATION: verb — бігти/бігати, noun — біг/пробіжка
PART_OF_SPEECH: Verb (дієслово), Noun (іменник)
PRONUNCIATION: /rʌn/ (BrE), /rʌn/ (AmE)
EXPLANATION_NOUN: An act of running or a period of running (біг, пробіжка)
EXPLANATION_VERB: To move rapidly on foot (бігти, рухатися швидко)
EXAMPLE_NOUN: I went for a morning run in the park. (Я пішов на ранкову пробіжку в парк.)
EXAMPLE_VERB: She likes to run every evening. (Вона любить бігати щовечора.)
"""