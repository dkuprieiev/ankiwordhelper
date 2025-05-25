import asyncio
import json
import requests
import subprocess
import time
import logging
import re
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("Please set TELEGRAM_BOT_TOKEN environment variable")

OLLAMA_URL = "http://localhost:11434/api/generate"
ANKI_URL = "http://localhost:8765"

# Global dictionary to store pending corrections per user
pending_corrections = {}

def check_anki_running():
    """Check if Anki is running"""
    try:
        response = requests.get(ANKI_URL, timeout=2)
        logger.info("Anki is running and responding")
        return True
    except Exception as e:
        logger.warning(f"Anki check failed: {e}")
        return False

def start_anki():
    """Start Anki in background"""
    try:
        logger.info("Attempting to start Anki process")
        subprocess.Popen(['anki'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)  # Wait for Anki to start
        logger.info("Anki process started")
        return True
    except Exception as e:
        logger.error(f"Failed to start Anki: {e}")
        return False

def sync_anki():
    """Trigger Anki sync"""
    try:
        logger.info("Triggering Anki sync")
        sync_data = {
            "action": "sync",
            "version": 6
        }
        response = requests.post(ANKI_URL, json=sync_data, timeout=30)
        result = response.json()

        if result.get("error"):
            logger.error(f"Sync error: {result['error']}")
            return False

        logger.info("Anki sync completed successfully")
        return True
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return False

def check_word_exists(word):
    """Check if word already exists in Anki"""
    try:
        logger.info(f"Checking if word '{word}' exists in Anki")
        search_data = {
            "action": "findNotes",
            "version": 6,
            "params": {
                "query": f"Front:{word}"
            }
        }
        response = requests.post(ANKI_URL, json=search_data, timeout=10)
        result = response.json()

        if result.get("error"):
            logger.error(f"Error searching for word: {result['error']}")
            return False

        notes = result.get("result", [])
        exists = len(notes) > 0
        logger.info(f"Word '{word}' exists: {exists} (found {len(notes)} notes)")
        return exists
    except Exception as e:
        logger.error(f"Error checking word existence: {e}")
        return False

def validate_card_content(word, translation, part_of_speech, pronunciation, explanation_noun, explanation_verb, example_noun, example_verb):
    """Validate if the generated card content is good quality"""
    issues = []

    # Check if essential fields are missing or too short
    if translation == "N/A" or len(translation) < 5:
        issues.append("Missing or too short translation")

    if part_of_speech == "N/A":
        issues.append("Missing part of speech")

    if pronunciation == "N/A" or "/" not in pronunciation:
        issues.append("Missing or invalid pronunciation")

    if explanation_noun == "N/A" and explanation_verb == "N/A":
        issues.append("Missing explanations")

    if example_noun == "N/A" and example_verb == "N/A":
        issues.append("Missing examples")

    # Check if word appears in examples
    word_in_examples = (word.lower() in example_noun.lower() if example_noun != "N/A" else False) or \
                      (word.lower() in example_verb.lower() if example_verb != "N/A" else False)

    if not word_in_examples:
        issues.append("Word not found in examples")

    # Check for Ukrainian content (basic check for Cyrillic characters)
    has_ukrainian = any('\u0400' <= char <= '\u04FF' for char in translation + explanation_noun + explanation_verb + example_noun + example_verb)
    if not has_ukrainian:
        issues.append("Missing Ukrainian translations")

    logger.info(f"Validation for '{word}': {len(issues)} issues found: {issues}")
    return len(issues) == 0, issues

def merge_card_attempts(word, attempts):
    """Merge multiple card generation attempts into one best version"""
    logger.info(f"Merging {len(attempts)} attempts for word '{word}'")

    # Extract best parts from all attempts
    translations = [a.get('translation', 'N/A') for a in attempts if a.get('translation') != 'N/A']
    pronunciations = [a.get('pronunciation', 'N/A') for a in attempts if a.get('pronunciation') != 'N/A' and '/' in a.get('pronunciation')]
    explanations_noun = [a.get('explanation_noun', 'N/A') for a in attempts if a.get('explanation_noun') != 'N/A']
    explanations_verb = [a.get('explanation_verb', 'N/A') for a in attempts if a.get('explanation_verb') != 'N/A']
    examples_noun = [a.get('example_noun', 'N/A') for a in attempts if a.get('example_noun') != 'N/A' and word.lower() in a.get('example_noun', '').lower()]
    examples_verb = [a.get('example_verb', 'N/A') for a in attempts if a.get('example_verb') != 'N/A' and word.lower() in a.get('example_verb', '').lower()]
    parts_of_speech = [a.get('part_of_speech', 'N/A') for a in attempts if a.get('part_of_speech') != 'N/A']

    # Pick the best (longest/most detailed) of each
    best_translation = max(translations, key=len) if translations else "N/A"
    best_pronunciation = pronunciations[0] if pronunciations else "N/A"
    best_explanation_noun = max(explanations_noun, key=len) if explanations_noun else "N/A"
    best_explanation_verb = max(explanations_verb, key=len) if explanations_verb else "N/A"
    best_example_noun = max(examples_noun, key=len) if examples_noun else "N/A"
    best_example_verb = max(examples_verb, key=len) if examples_verb else "N/A"
    best_part_of_speech = max(parts_of_speech, key=len) if parts_of_speech else "N/A"

    logger.info("Merged card created successfully")
    return {
        'translation': best_translation,
        'part_of_speech': best_part_of_speech,
        'pronunciation': best_pronunciation,
        'explanation_noun': best_explanation_noun,
        'explanation_verb': best_explanation_verb,
        'example_noun': best_example_noun,
        'example_verb': best_example_verb
    }

async def generate_card_with_retry(word, update, max_attempts=4):
    """Generate card content with validation and retry logic"""
    attempts = []

    # Enhanced prompt for detailed card
    prompt = f"""For the English word "{word}", create a vocabulary card with this EXACT structure. Do NOT use markdown formatting like ** or *:

TRANSLATION: (part of speech) — [Ukrainian translation], (part of speech) — [Ukrainian translation if multiple meanings]
PART_OF_SPEECH: [Main part of speech] (Ukrainian) & [Secondary if applicable] (Ukrainian)
PRONUNCIATION: /[IPA British]/ (BrE), /[IPA American]/ (AmE)
EXPLANATION_NOUN: [English explanation] (Ukrainian explanation)
EXPLANATION_VERB: [English explanation] (Ukrainian explanation) (if applicable)
EXAMPLE_NOUN: [English sentence with word] (Ukrainian translation)
EXAMPLE_VERB: [English sentence with word] (Ukrainian translation) (if applicable)

Use only plain text, no bold formatting, no asterisks, no markdown symbols."""

    ollama_data = {
        "model": "gemma3:4b",
        "prompt": prompt,
        "stream": False
    }

    for attempt in range(max_attempts):
        try:
            logger.info(f"Generation attempt {attempt + 1}/{max_attempts} for word '{word}'")
            await update.message.reply_text(f"🔄 Generating flashcard... (attempt {attempt + 1}/{max_attempts})")

            response = requests.post(OLLAMA_URL, json=ollama_data, timeout=60)
            raw_content = response.json()["response"].strip()

            # Parse the structured response
            lines = raw_content.split('\n')
            translation = part_of_speech = pronunciation = explanation_noun = explanation_verb = example_noun = example_verb = "N/A"

            for line in lines:
                line = line.strip()
                if line.startswith('TRANSLATION:'):
                    translation = line.replace('TRANSLATION:', '').strip()
                elif line.startswith('PART_OF_SPEECH:'):
                    part_of_speech = line.replace('PART_OF_SPEECH:', '').strip()
                elif line.startswith('PRONUNCIATION:'):
                    pronunciation = line.replace('PRONUNCIATION:', '').strip()
                elif line.startswith('EXPLANATION_NOUN:'):
                    explanation_noun = line.replace('EXPLANATION_NOUN:', '').strip()
                elif line.startswith('EXPLANATION_VERB:'):
                    explanation_verb = line.replace('EXPLANATION_VERB:', '').strip()
                elif line.startswith('EXAMPLE_NOUN:'):
                    example_noun = line.replace('EXAMPLE_NOUN:', '').strip()
                elif line.startswith('EXAMPLE_VERB:'):
                    example_verb = line.replace('EXAMPLE_VERB:', '').strip()

            # Store this attempt
            attempt_data = {
                'translation': translation,
                'part_of_speech': part_of_speech,
                'pronunciation': pronunciation,
                'explanation_noun': explanation_noun,
                'explanation_verb': explanation_verb,
                'example_noun': example_noun,
                'example_verb': example_verb
            }
            attempts.append(attempt_data)

            # Validate the content
            is_valid, issues = validate_card_content(word, translation, part_of_speech, pronunciation,
                                                   explanation_noun, explanation_verb, example_noun, example_verb)

            if is_valid:
                logger.info(f"Valid card generated on attempt {attempt + 1}")
                await update.message.reply_text("✅ Quality card generated!")
                return attempt_data
            else:
                logger.warning(f"Attempt {attempt + 1} failed validation: {issues}")
                await update.message.reply_text(f"⚠️ Issues found: {', '.join(issues[:2])}...")

        except Exception as e:
            logger.error(f"Error in generation attempt {attempt + 1}: {e}")
            await update.message.reply_text(f"❌ Generation error on attempt {attempt + 1}")

    # If all attempts failed, merge the best parts
    logger.info(f"All {max_attempts} attempts failed, merging best parts")
    await update.message.reply_text("🔧 Merging best parts from all attempts...")
    return merge_card_attempts(word, attempts)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    logger.info(f"Start command from user {update.effective_user.id}")

    # Check Anki status
    if check_anki_running():
        await update.message.reply_text("✅ Anki is already running!")
        logger.info("Anki already running")
    else:
        await update.message.reply_text("🚀 Starting Anki...")
        logger.info("Starting Anki...")

        if start_anki():
            # Wait for Anki to fully start
            for i in range(10):
                await asyncio.sleep(1)
                if check_anki_running():
                    await update.message.reply_text("✅ Anki started successfully!")
                    logger.info("Anki started successfully")
                    break
            else:
                await update.message.reply_text("❌ Failed to start Anki!")
                logger.error("Failed to start Anki")
        else:
            await update.message.reply_text("❌ Failed to start Anki!")
            logger.error("Failed to start Anki process")

async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sync command"""
    logger.info(f"Manual sync command from user {update.effective_user.id}")
    await update.message.reply_text("🔄 Syncing Anki...")

    if not check_anki_running():
        await update.message.reply_text("❌ Anki is not running!")
        logger.warning("Sync failed: Anki not running")
        return

    logger.info("Starting manual sync...")
    if sync_anki():
        await update.message.reply_text("✅ Anki sync completed!")
        logger.info("Manual sync completed successfully")
    else:
        await update.message.reply_text("❌ Anki sync failed!")
        logger.error("Manual sync failed")

async def check_and_correct_spelling(word, update):
    """Check spelling and suggest correction if needed"""
    # Basic validation - only letters and common characters
    if not re.match(r'^[a-zA-Z\-\']+$', word):
        await update.message.reply_text(f"⚠️ '{word}' contains invalid characters. Please send only English words.")
        return None

    # Length validation
    if len(word) < 2 or len(word) > 30:
        await update.message.reply_text(f"⚠️ '{word}' seems too {'short' if len(word) < 2 else 'long'}. Please check the spelling.")
        return None

    try:
        logger.info(f"Checking spelling for word '{word}'")

        # Use Ollama to check spelling and suggest correction
        spell_check_prompt = f"""Check if the English word "{word}" is spelled correctly.

If it's correct, respond with: CORRECT
If it's misspelled, respond with: CORRECTION: [correct spelling]

Only provide one word corrections for common English words. Examples:
- "recieve" -> CORRECTION: receive
- "seperate" -> CORRECTION: separate
- "definately" -> CORRECTION: definitely
- "hello" -> CORRECT"""

        ollama_data = {
            "model": "gemma3:4b",
            "prompt": spell_check_prompt,
            "stream": False
        }

        response = requests.post(OLLAMA_URL, json=ollama_data, timeout=20)
        spell_result = response.json()["response"].strip()

        logger.info(f"Spell check result for '{word}': {spell_result}")

        if "CORRECT" in spell_result.upper():
            logger.info(f"Word '{word}' is spelled correctly")
            return word
        elif "CORRECTION:" in spell_result.upper():
            # Extract the corrected word
            correction_part = spell_result.split("CORRECTION:")[-1].strip()
            corrected_word = re.findall(r'\b[a-zA-Z\-\']+\b', correction_part)

            if corrected_word:
                suggested_word = corrected_word[0].lower()
                logger.info(f"Suggesting correction: '{word}' -> '{suggested_word}'")

                # Ask user for confirmation
                await update.message.reply_text(
                    f"🔍 Did you mean **{suggested_word}** instead of '{word}'?\n"
                    f"Reply with:\n"
                    f"• **yes** - to use '{suggested_word}'\n"
                    f"• **no** - to keep '{word}'\n"
                    f"• **cancel** - to cancel"
                )

                return "WAIT_FOR_CONFIRMATION", suggested_word
            else:
                logger.warning(f"Could not extract correction from: {spell_result}")
                return word
        else:
            logger.info(f"Unclear spell check result, proceeding with original word: {word}")
            return word

    except Exception as e:
        logger.error(f"Spell check failed for '{word}': {e}")
        await update.message.reply_text("⚠️ Spell check failed, proceeding with your word...")
        return word

async def handle_spell_correction_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user response to spell correction suggestion"""
    user_id = update.effective_user.id
    response = update.message.text.strip().lower()

    if user_id not in pending_corrections:
        return False  # Not a spell correction response

    original_word, suggested_word = pending_corrections[user_id]

    if response in ['yes', 'y']:
        await update.message.reply_text(f"✅ Using corrected word: **{suggested_word}**")
        logger.info(f"User accepted correction: '{original_word}' -> '{suggested_word}'")
        del pending_corrections[user_id]
        return suggested_word
    elif response in ['no', 'n']:
        await update.message.reply_text(f"✅ Keeping original word: **{original_word}**")
        logger.info(f"User rejected correction, keeping: '{original_word}'")
        del pending_corrections[user_id]
        return original_word
    elif response in ['cancel', 'c']:
        await update.message.reply_text("❌ Cancelled")
        logger.info(f"User cancelled spell correction for: '{original_word}'")
        del pending_corrections[user_id]
        return None
    else:
        await update.message.reply_text("Please respond with **yes**, **no**, or **cancel**")
        return False  # Keep waiting for valid response

async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process a word and add it to Anki"""
    word = update.message.text.strip()
    user_id = update.effective_user.id

    # Check if this is a response to spell correction
    if user_id in pending_corrections:
        corrected_word = await handle_spell_correction_response(update, context)
        if corrected_word is False:
            return  # Still waiting for valid response
        elif corrected_word is None:
            return  # User cancelled
        else:
            word = corrected_word  # Use the corrected word
    else:
        # Check spelling for new words
        spell_result = await check_and_correct_spelling(word, update)

        if spell_result is None:
            return  # Invalid word or error
        elif isinstance(spell_result, tuple) and spell_result[0] == "WAIT_FOR_CONFIRMATION":
            # Store pending correction and wait for user response
            pending_corrections[user_id] = (word, spell_result[1])
            return
        else:
            word = spell_result  # Use the (possibly corrected) word

    logger.info(f"Processing word '{word}' from user {user_id}")

    # Check if Anki is running, start if not
    if not check_anki_running():
        logger.warning("Anki not running, attempting to start...")
        await update.message.reply_text("⚠️ Starting Anki...")

        if not start_anki():
            await update.message.reply_text("❌ Failed to start Anki!")
            logger.error("Failed to start Anki process")
            return

        # Wait and check again
        for i in range(6):  # Wait up to 30 seconds
            await asyncio.sleep(5)
            if check_anki_running():
                logger.info(f"Anki started after {(i+1)*5} seconds")
                break

        if not check_anki_running():
            await update.message.reply_text("❌ Anki failed to start!")
            logger.error("Anki failed to start within timeout")
            return

    # Check if word already exists
    if check_word_exists(word):
        await update.message.reply_text(f"⚠️ Word '{word}' already exists in Anki deck!")
        logger.info(f"Word '{word}' already exists, skipping")
        return

    try:
        # Generate card content with validation and retry
        card_data = await generate_card_with_retry(word, update)

        # Build examples section
        examples_section = ""
        if card_data['example_noun'] != "N/A":
            examples_section += f"• <b>Noun:</b> {card_data['example_noun']}<br>"
        if card_data['example_verb'] != "N/A":
            examples_section += f"• <b>Verb:</b> {card_data['example_verb']}<br>"

        # Build explanation section
        explanation_section = ""
        if card_data['explanation_noun'] != "N/A":
            explanation_section += f"🔹 As a <b>noun</b>: {card_data['explanation_noun']}<br>"
        if card_data['explanation_verb'] != "N/A":
            explanation_section += f"🔹 As a <b>verb</b>: {card_data['explanation_verb']}<br>"

        # Format for Anki HTML
        formatted_content = f"""<b>1. Translation (Ukrainian):</b><br>
{card_data['translation']}<br><br>

<b>2. Part of Speech:</b><br>
{card_data['part_of_speech']}<br><br>

<b>3. Pronunciation (IPA):</b><br>
{card_data['pronunciation']}<br><br>

<b>4. Explanation (English + Ukrainian):</b><br>
{explanation_section}<br>

<b>5. Examples (Приклади):</b><br>
{examples_section}"""

        # Add to Anki
        logger.info(f"Adding card to Anki for word '{word}'")
        anki_data = {
            "action": "addNote",
            "version": 6,
            "params": {
                "note": {
                    "deckName": "Default",
                    "modelName": "Basic",
                    "fields": {
                        "Front": word,
                        "Back": formatted_content
                    }
                }
            }
        }

        anki_response = requests.post(ANKI_URL, json=anki_data)

        if anki_response.json().get("error"):
            error_msg = anki_response.json()['error']
            await update.message.reply_text(f"Error adding to Anki: {error_msg}")
            logger.error(f"Error adding card: {error_msg}")
        else:
            await update.message.reply_text(f"✅ Added '{word}' to Anki!")
            logger.info(f"Successfully added card for word '{word}'")

            # Auto-sync after adding card
            await update.message.reply_text("🔄 Auto-syncing...")
            logger.info("Starting auto-sync after card addition")

            if sync_anki():
                await update.message.reply_text("✅ Sync completed!")
                logger.info("Auto-sync completed successfully")
            else:
                await update.message.reply_text("⚠️ Sync failed (card still added locally)")
                logger.warning("Auto-sync failed, but card was added locally")

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Exception in add_word: {e}")

def main():
    logger.info("Starting Anki Telegram Bot")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("sync", sync_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_word))

    logger.info("Bot handlers registered, starting polling...")
    app.run_polling()

if __name__ == "__main__":
    main()