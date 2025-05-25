"""Card generation using Ollama."""

import logging
import re
from typing import Dict, List, Optional
import requests
import asyncio
from dataclasses import dataclass

from config import settings, FEW_SHOT_EXAMPLES
from validators import CardValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class CardData:
    """Structured card data."""
    word: str
    translation: str = "N/A"
    part_of_speech: str = "N/A"
    pronunciation: str = "N/A"
    explanation_noun: str = "N/A"
    explanation_verb: str = "N/A"
    example_noun: str = "N/A"
    example_verb: str = "N/A"

    def to_dict(self) -> Dict[str, str]:
        return {
            'word': self.word,
            'translation': self.translation,
            'part_of_speech': self.part_of_speech,
            'pronunciation': self.pronunciation,
            'explanation_noun': self.explanation_noun,
            'explanation_verb': self.explanation_verb,
            'example_noun': self.example_noun,
            'example_verb': self.example_verb
        }


class CardGenerator:
    """Generate Anki cards using Ollama."""

    def __init__(self):
        self.validator = CardValidator()

    def _create_prompt(self, word: str) -> str:
        """Create detailed prompt for card generation."""
        return f"""Create a vocabulary card for the English word "{word}".

CRITICAL RULES:
1. Use ONLY plain text. Do NOT use ** or * or any markdown formatting.
2. Each line must start with the exact label shown below.
3. If the word cannot be used as noun or verb, write "N/A" for those fields.
4. Always include Ukrainian translations in Cyrillic script.

{FEW_SHOT_EXAMPLES}

Now create a card for "{word}" following this EXACT format:
TRANSLATION: [part of speech] — [Ukrainian translation]
PART_OF_SPEECH: [Primary part of speech in English] ([Ukrainian translation])
PRONUNCIATION: /[IPA British]/ (BrE), /[IPA American]/ (AmE)
EXPLANATION_NOUN: [IF word can be a noun: English explanation] ([Ukrainian explanation])
EXPLANATION_VERB: [IF word can be a verb: English explanation] ([Ukrainian explanation])
EXAMPLE_NOUN: [IF word can be a noun: English sentence with the word] ([Ukrainian translation])
EXAMPLE_VERB: [IF word can be a verb: English sentence with the word] ([Ukrainian translation])"""

    def _parse_response(self, response: str, word: str) -> CardData:
        """Parse Ollama response into structured data."""
        lines = response.strip().split('\n')
        card = CardData(word=word)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith('TRANSLATION:'):
                card.translation = line.replace('TRANSLATION:', '').strip()
            elif line.startswith('PART_OF_SPEECH:'):
                card.part_of_speech = line.replace('PART_OF_SPEECH:', '').strip()
            elif line.startswith('PRONUNCIATION:'):
                card.pronunciation = line.replace('PRONUNCIATION:', '').strip()
            elif line.startswith('EXPLANATION_NOUN:'):
                card.explanation_noun = line.replace('EXPLANATION_NOUN:', '').strip()
            elif line.startswith('EXPLANATION_VERB:'):
                card.explanation_verb = line.replace('EXPLANATION_VERB:', '').strip()
            elif line.startswith('EXAMPLE_NOUN:'):
                card.example_noun = line.replace('EXAMPLE_NOUN:', '').strip()
            elif line.startswith('EXAMPLE_VERB:'):
                card.example_verb = line.replace('EXAMPLE_VERB:', '').strip()

        return card

    def _generate_missing_examples(self, word: str, card_data: Dict[str, str]) -> Dict[str, str]:
        """Generate examples if they're missing."""
        if card_data['example_noun'] == "N/A" and card_data['example_verb'] == "N/A":
            logger.info(f"Generating missing examples for '{word}'")

            try:
                # Determine which type of example to generate
                if card_data['explanation_noun'] != "N/A":
                    example_type = "noun"
                elif card_data['explanation_verb'] != "N/A":
                    example_type = "verb"
                else:
                    example_type = "general"

                prompt = f"""Generate ONE example sentence using the word "{word}" as a {example_type}.
Format: [English sentence] ([Ukrainian translation])
The sentence should be simple and clearly demonstrate the word's meaning.
Do not use any markdown formatting."""

                response = requests.post(
                    settings.ollama_url,
                    json={
                        "model": settings.ollama_model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=30
                )

                example = response.json()["response"].strip()
                example = self.validator.clean_markdown(example)

                if example_type == "noun":
                    card_data['example_noun'] = example
                elif example_type == "verb":
                    card_data['example_verb'] = example
                else:
                    # Try to determine from the generated example
                    if card_data['explanation_noun'] != "N/A":
                        card_data['example_noun'] = example
                    else:
                        card_data['example_verb'] = example

            except Exception as e:
                logger.error(f"Failed to generate examples: {e}")

        return card_data

    async def generate_single_attempt(self, word: str) -> Optional[CardData]:
        """Generate a single card attempt."""
        try:
            prompt = self._create_prompt(word)

            response = requests.post(
                settings.ollama_url,
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=settings.generation_timeout
            )

            raw_content = response.json()["response"]
            card = self._parse_response(raw_content, word)

            return card

        except Exception as e:
            logger.error(f"Generation attempt failed: {e}")
            return None

    def merge_attempts(self, word: str, attempts: List[CardData]) -> CardData:
        """Merge multiple attempts into best version."""
        logger.info(f"Merging {len(attempts)} attempts for word '{word}'")

        # Extract all non-N/A values for each field
        translations = [a.translation for a in attempts if a.translation != "N/A"]
        pronunciations = [a.pronunciation for a in attempts
                         if a.pronunciation != "N/A" and '/' in a.pronunciation]
        explanations_noun = [a.explanation_noun for a in attempts if a.explanation_noun != "N/A"]
        explanations_verb = [a.explanation_verb for a in attempts if a.explanation_verb != "N/A"]
        examples_noun = [a.example_noun for a in attempts
                        if a.example_noun != "N/A" and word.lower() in a.example_noun.lower()]
        examples_verb = [a.example_verb for a in attempts
                        if a.example_verb != "N/A" and word.lower() in a.example_verb.lower()]
        parts_of_speech = [a.part_of_speech for a in attempts if a.part_of_speech != "N/A"]

        # Select best values (longest with Ukrainian content preferred)
        def select_best(values: List[str]) -> str:
            if not values:
                return "N/A"
            # Prefer values with Cyrillic characters
            cyrillic_values = [v for v in values
                              if any('\u0400' <= char <= '\u04FF' for char in v)]
            if cyrillic_values:
                return max(cyrillic_values, key=len)
            return max(values, key=len)

        merged = CardData(
            word=word,
            translation=select_best(translations),
            part_of_speech=select_best(parts_of_speech),
            pronunciation=pronunciations[0] if pronunciations else "N/A",
            explanation_noun=select_best(explanations_noun),
            explanation_verb=select_best(explanations_verb),
            example_noun=select_best(examples_noun),
            example_verb=select_best(examples_verb)
        )

        return merged

    async def generate_with_retry(self, word: str, max_attempts: int = None) -> Dict[str, str]:
        """Generate card with validation and retry logic."""
        if max_attempts is None:
            max_attempts = settings.max_generation_attempts

        attempts = []

        for attempt_num in range(max_attempts):
            logger.info(f"Generation attempt {attempt_num + 1}/{max_attempts} for '{word}'")

            card = await self.generate_single_attempt(word)
            if card:
                attempts.append(card)

                # Clean the data
                card_dict = self.validator.clean_card_data(card.to_dict())

                # Validate
                validation = self.validator.validate_card_content(word, card_dict)

                if validation.is_valid:
                    logger.info(f"Valid card generated on attempt {attempt_num + 1}")
                    # Try to add examples if missing
                    card_dict = self._generate_missing_examples(word, card_dict)
                    return card_dict
                else:
                    logger.warning(f"Attempt {attempt_num + 1} validation issues: {validation.issues}")

        # If all attempts failed, merge best parts
        if attempts:
            logger.info("All attempts failed validation, merging best parts")
            merged = self.merge_attempts(word, attempts)
            card_dict = self.validator.clean_card_data(merged.to_dict())
            card_dict = self._generate_missing_examples(word, card_dict)
            return card_dict

        # Fallback if no attempts succeeded
        logger.error(f"All generation attempts failed for '{word}'")
        return CardData(word=word).to_dict()

    def format_for_anki(self, card_data: Dict[str, str]) -> str:
        """Format card data as HTML for Anki."""
        # Build examples section
        examples_section = ""
        if card_data['example_noun'] != "N/A":
            examples_section += f"• <b>Noun:</b> {card_data['example_noun']}<br>"
        if card_data['example_verb'] != "N/A":
            examples_section += f"• <b>Verb:</b> {card_data['example_verb']}<br>"

        if not examples_section:
            examples_section = "<i>No examples available</i><br>"

        # Build explanation section
        explanation_section = ""
        if card_data['explanation_noun'] != "N/A":
            explanation_section += f"🔹 As a <b>noun</b>: {card_data['explanation_noun']}<br>"
        if card_data['explanation_verb'] != "N/A":
            explanation_section += f"🔹 As a <b>verb</b>: {card_data['explanation_verb']}<br>"

        if not explanation_section:
            explanation_section = "<i>No explanation available</i><br>"

        # Format for Anki HTML
        formatted_content = f"""<b>1. Translation (Переклад):</b><br>
{card_data.get('translation', 'N/A')}<br><br>

<b>2. Part of Speech (Частина мови):</b><br>
{card_data.get('part_of_speech', 'N/A')}<br><br>

<b>3. Pronunciation (Вимова):</b><br>
{card_data.get('pronunciation', 'N/A')}<br><br>

<b>4. Explanation (Пояснення):</b><br>
{explanation_section}<br>

<b>5. Examples (Приклади):</b><br>
{examples_section}"""

        return formatted_content