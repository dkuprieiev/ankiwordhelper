"""Spell checking utilities."""

import re
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass
from spellchecker import SpellChecker
import requests

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class SpellCheckResult:
    """Result of spell checking."""
    is_valid: bool
    original: str
    suggestion: Optional[str] = None


class EnhancedSpellChecker:
    """Enhanced spell checker with multiple strategies."""

    def __init__(self):
        self.spell_checker = SpellChecker()
        # Add common English words that might be missing
        self.spell_checker.word_frequency.load_words([
            'covid', 'blockchain', 'cryptocurrency', 'metadata',
            'smartphone', 'email', 'online', 'website'
        ])

    def validate_word_format(self, word: str) -> Tuple[bool, Optional[str]]:
        """Validate word format and characters."""
        # Check for valid characters
        if not re.match(r'^[a-zA-Z\-\']+$', word):
            return False, "Contains invalid characters (only letters, hyphens, and apostrophes allowed)"

        # Check length
        if len(word) < 2:
            return False, "Word is too short (minimum 2 characters)"

        if len(word) > 30:
            return False, "Word is too long (maximum 30 characters)"

        # Check if it's just a greeting or interjection
        greetings = {'hi', 'hello', 'hey', 'bye', 'goodbye', 'ok', 'okay', 'yes', 'no', 'yeah', 'nah'}
        if word.lower() in greetings:
            return False, f"'{word}' is a greeting/interjection. Please send vocabulary words you'd like to learn."

        return True, None

    def check_with_pyspellchecker(self, word: str) -> SpellCheckResult:
        """Check spelling using pyspellchecker library."""
        word_lower = word.lower()

        # Check if word is known
        if word_lower in self.spell_checker:
            return SpellCheckResult(is_valid=True, original=word)

        # Get correction
        correction = self.spell_checker.correction(word_lower)

        if correction and correction != word_lower:
            # Preserve original capitalization pattern
            if word[0].isupper():
                correction = correction.capitalize()
            return SpellCheckResult(is_valid=False, original=word, suggestion=correction)

        # If no correction found, it might be a valid word not in dictionary
        return SpellCheckResult(is_valid=True, original=word)

    def check_with_ollama(self, word: str) -> Optional[SpellCheckResult]:
        """Fallback to Ollama for spell checking complex words."""
        try:
            prompt = f"""Check if the English word "{word}" is spelled correctly.

If it's correct, respond with: CORRECT
If it's misspelled, respond with: CORRECTION: [correct spelling]

Only correct obvious misspellings. Examples:
- "recieve" -> CORRECTION: receive
- "necessary" -> CORRECT
- "definately" -> CORRECTION: definitely"""

            response = requests.post(
                settings.ollama_url,
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=settings.spell_check_timeout
            )

            result = response.json()["response"].strip()

            if "CORRECT" in result.upper():
                return SpellCheckResult(is_valid=True, original=word)
            elif "CORRECTION:" in result.upper():
                correction_part = result.split("CORRECTION:")[-1].strip()
                corrected_words = re.findall(r'\b[a-zA-Z\-\']+\b', correction_part)

                if corrected_words:
                    suggestion = corrected_words[0]
                    # Preserve capitalization
                    if word[0].isupper():
                        suggestion = suggestion.capitalize()
                    return SpellCheckResult(is_valid=False, original=word, suggestion=suggestion)

        except Exception as e:
            logger.error(f"Ollama spell check failed: {e}")

        return None

    def check_spelling(self, word: str) -> SpellCheckResult:
        """Check spelling using multiple strategies."""
        # First validate format
        valid_format, error_msg = self.validate_word_format(word)
        if not valid_format:
            logger.info(f"Word '{word}' validation: {error_msg}")
            # For greetings, return as invalid with no suggestion
            if "greeting" in error_msg.lower():
                return SpellCheckResult(is_valid=False, original=word, suggestion=None)
            return SpellCheckResult(is_valid=False, original=word)

        # Try pyspellchecker first
        result = self.check_with_pyspellchecker(word)

        # If pyspellchecker is unsure, try Ollama
        if not result.is_valid and result.suggestion == word.lower():
            ollama_result = self.check_with_ollama(word)
            if ollama_result:
                return ollama_result

        return result

    def get_word_suggestions(self, word: str, max_suggestions: int = 3) -> List[str]:
        """Get multiple spelling suggestions for a word."""
        candidates = self.spell_checker.candidates(word.lower())

        if not candidates:
            return []

        # Sort by edit distance and frequency
        suggestions = sorted(candidates,
                            key=lambda x: (self.spell_checker.distance(word.lower(), x),
                                          -self.spell_checker.word_frequency[x]))

        # Preserve capitalization
        if word[0].isupper():
            suggestions = [s.capitalize() for s in suggestions]

        return suggestions[:max_suggestions]