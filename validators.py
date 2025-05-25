"""Validation logic for card content."""

import re
import logging
from typing import Tuple, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of card validation."""
    is_valid: bool
    issues: List[str]
    quality_score: float  # 0.0 to 1.0
    suggestions: List[str]


class CardValidator:
    """Validator for Anki card content."""

    @staticmethod
    def clean_markdown(text: str) -> str:
        """Remove any markdown formatting that slipped through."""
        if text == "N/A":
            return text

        # Remove bold markers
        text = text.replace('**', '')
        text = text.replace('*', '')

        # Remove links [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove headers
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        return text.strip()

    @staticmethod
    def validate_pronunciation(pronunciation: str) -> Tuple[bool, str]:
        """Validate IPA pronunciation format."""
        if pronunciation == "N/A":
            return False, "Missing pronunciation"

        # Check for IPA markers
        if not ('/' in pronunciation or '[' in pronunciation):
            return False, "Invalid IPA format (missing / or [ markers)"

        # Check for BrE and AmE
        if not ('BrE' in pronunciation and 'AmE' in pronunciation):
            return False, "Missing British or American pronunciation"

        return True, ""

    @staticmethod
    def validate_translation(translation: str) -> Tuple[bool, str]:
        """Validate Ukrainian translation."""
        if translation == "N/A" or len(translation) < 5:
            return False, "Missing or too short translation"

        # Check for Ukrainian content (Cyrillic characters)
        has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in translation)
        if not has_cyrillic:
            return False, "Missing Ukrainian (Cyrillic) characters in translation"

        return True, ""

    @staticmethod
    def validate_examples(word: str, example_noun: str, example_verb: str) -> List[str]:
        """Validate example sentences."""
        issues = []

        if example_noun == "N/A" and example_verb == "N/A":
            issues.append("No examples provided")
            return issues

        # Check if word appears in examples
        if example_noun != "N/A":
            # Check various forms of the word
            word_forms = [word.lower(), word.lower() + 's', word.lower() + 'ed',
                         word.lower() + 'ing', word.lower()[:-1] + 'ied']
            if not any(form in example_noun.lower() for form in word_forms):
                issues.append(f"Word '{word}' not found in noun example")

        if example_verb != "N/A":
            word_forms = [word.lower(), word.lower() + 's', word.lower() + 'ed',
                         word.lower() + 'ing', word.lower()[:-1] + 'ied']
            if not any(form in example_verb.lower() for form in word_forms):
                issues.append(f"Word '{word}' not found in verb example")

        # Check for Ukrainian translations in examples
        for example, example_type in [(example_noun, "noun"), (example_verb, "verb")]:
            if example != "N/A":
                has_cyrillic = any('\u0400' <= char <= '\u04FF' for char in example)
                if not has_cyrillic:
                    issues.append(f"Missing Ukrainian translation in {example_type} example")

        return issues

    @classmethod
    def validate_card_content(cls, word: str, card_data: Dict[str, str]) -> ValidationResult:
        """Comprehensive validation of card content."""
        issues = []
        suggestions = []
        quality_points = 0
        max_points = 10

        # Extract fields
        translation = card_data.get('translation', 'N/A')
        part_of_speech = card_data.get('part_of_speech', 'N/A')
        pronunciation = card_data.get('pronunciation', 'N/A')
        explanation_noun = card_data.get('explanation_noun', 'N/A')
        explanation_verb = card_data.get('explanation_verb', 'N/A')
        example_noun = card_data.get('example_noun', 'N/A')
        example_verb = card_data.get('example_verb', 'N/A')

        # Check for markdown in all fields
        all_fields = [translation, part_of_speech, pronunciation,
                     explanation_noun, explanation_verb, example_noun, example_verb]

        if any('**' in field or '*' in field for field in all_fields if field != "N/A"):
            issues.append("Contains markdown formatting")
            suggestions.append("Remove all ** and * characters from the content")
        else:
            quality_points += 1

        # Validate translation
        valid, issue = cls.validate_translation(translation)
        if not valid:
            issues.append(issue)
            suggestions.append("Ensure Ukrainian translation is provided with Cyrillic characters")
        else:
            quality_points += 2

        # Validate part of speech
        if part_of_speech == "N/A":
            issues.append("Missing part of speech")
            suggestions.append("Specify whether the word is a noun, verb, adjective, etc.")
        else:
            quality_points += 1

        # Validate pronunciation
        valid, issue = cls.validate_pronunciation(pronunciation)
        if not valid:
            issues.append(issue)
            suggestions.append("Provide IPA pronunciation for both British and American English")
        else:
            quality_points += 2

        # Validate explanations
        if explanation_noun == "N/A" and explanation_verb == "N/A":
            issues.append("No explanations provided")
            suggestions.append("Provide at least one explanation for the word's meaning")
        else:
            quality_points += 2

        # Validate examples
        example_issues = cls.validate_examples(word, example_noun, example_verb)
        if example_issues:
            issues.extend(example_issues)
            suggestions.append("Ensure examples contain the word and include Ukrainian translations")
        else:
            quality_points += 2

        # Calculate quality score
        quality_score = quality_points / max_points

        # Determine if valid
        is_valid = len(issues) == 0 or (quality_score >= 0.6 and len(issues) <= 2)

        logger.info(f"Validation for '{word}': score={quality_score:.2f}, "
                   f"issues={len(issues)}, valid={is_valid}")

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            quality_score=quality_score,
            suggestions=suggestions
        )

    @staticmethod
    def clean_card_data(card_data: Dict[str, str]) -> Dict[str, str]:
        """Clean all fields in card data."""
        cleaned = {}
        for key, value in card_data.items():
            cleaned[key] = CardValidator.clean_markdown(value)
        return cleaned