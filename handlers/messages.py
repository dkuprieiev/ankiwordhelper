"""Message handlers for processing words."""

import logging
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from anki_client import AnkiClient
from card_generator import CardGenerator
from utils import SessionManager, EnhancedSpellChecker
from config import settings

logger = logging.getLogger(__name__)


async def handle_spell_correction_response(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session_manager: SessionManager,
    user_id: int
) -> Optional[str]:
    """Handle user response to spell correction suggestion."""
    response = update.message.text.strip().lower()
    pending = session_manager.get_pending_correction(user_id)

    if not pending:
        return None

    original_word, suggested_word = pending

    if response in ['yes', 'y']:
        await update.message.reply_text(f"✅ Using corrected word: **{suggested_word}**",
                                      parse_mode='Markdown')
        logger.info(f"User {user_id} accepted correction: '{original_word}' -> '{suggested_word}'")
        session_manager.clear_pending_correction(user_id)
        return suggested_word

    elif response in ['no', 'n']:
        await update.message.reply_text(f"✅ Keeping original word: **{original_word}**",
                                      parse_mode='Markdown')
        logger.info(f"User {user_id} rejected correction, keeping: '{original_word}'")
        session_manager.clear_pending_correction(user_id)
        return original_word

    elif response in ['cancel', 'c']:
        await update.message.reply_text("❌ Cancelled")
        logger.info(f"User {user_id} cancelled spell correction")
        session_manager.clear_pending_correction(user_id)
        return ""  # Empty string signals cancellation

    else:
        await update.message.reply_text(
            "Please respond with:\n"
            "• **yes** or **y** - to accept the suggestion\n"
            "• **no** or **n** - to keep your original word\n"
            "• **cancel** or **c** - to cancel",
            parse_mode='Markdown'
        )
        return None  # Keep waiting


async def process_word(
    word: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    anki_client: AnkiClient,
    card_generator: CardGenerator,
    session_manager: SessionManager
):
    """Process a word and add it to Anki."""
    user_id = update.effective_user.id

    logger.info(f"Processing word '{word}' from user {user_id}")

    # Ensure Anki is running
    if not anki_client.ensure_running():
        await update.message.reply_text(
            "⚠️ Starting Anki...\n"
            "Please wait a moment and try again."
        )
        return

    # Check if word already exists
    if anki_client.word_exists(word):
        await update.message.reply_text(
            f"⚠️ Word '**{word}**' already exists in your Anki deck!",
            parse_mode='Markdown'
        )
        logger.info(f"Word '{word}' already exists, skipping")
        return

    try:
        # Track attempts
        attempt_count = session_manager.increment_generation_attempts(user_id, word)

        # Generate card with progress updates
        await update.message.reply_text(
            f"🔄 Generating flashcard for '**{word}**'...\n"
            f"This may take a moment.",
            parse_mode='Markdown'
        )

        # Generate card
        card_data = await card_generator.generate_with_retry(word)

        # Format for Anki
        formatted_content = card_generator.format_for_anki(card_data)

        # Add to Anki
        result = anki_client.add_note(word, formatted_content)

        if result['success']:
            # Clear attempt counter on success
            session_manager.reset_generation_attempts(user_id, word)

            # Success message with preview
            success_msg = f"✅ Added '**{word}**' to Anki!\n\n"

            # Add brief preview
            if card_data.get('translation') != 'N/A':
                success_msg += f"📝 Translation: {card_data['translation']}\n"
            if card_data.get('pronunciation') != 'N/A':
                # Extract just the first pronunciation
                pron = card_data['pronunciation'].split(',')[0].strip()
                success_msg += f"🔊 Pronunciation: {pron}\n"

            await update.message.reply_text(success_msg, parse_mode='Markdown')

            # Auto-sync
            await update.message.reply_text("🔄 Auto-syncing...")
            if anki_client.sync():
                await update.message.reply_text("✅ Sync completed!")
            else:
                await update.message.reply_text("⚠️ Sync failed (card still saved locally)")

        else:
            error_msg = result.get('error', 'Unknown error')
            await update.message.reply_text(
                f"❌ Failed to add card: {error_msg}\n"
                f"Please try again or check your Anki settings."
            )
            logger.error(f"Failed to add card for '{word}': {error_msg}")

    except Exception as e:
        logger.error(f"Exception processing word '{word}': {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ An error occurred while processing '**{word}**'.\n"
            f"Please try again later.",
            parse_mode='Markdown'
        )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    if not update.message or not update.message.text:
        return

    word = update.message.text.strip()
    user_id = update.effective_user.id

    # Get services from context
    session_manager: SessionManager = context.bot_data['session_manager']
    spell_checker: EnhancedSpellChecker = context.bot_data['spell_checker']
    anki_client: AnkiClient = context.bot_data['anki_client']
    card_generator: CardGenerator = context.bot_data['card_generator']

    # Check if this is a response to spell correction
    if session_manager.get_pending_correction(user_id):
        corrected_word = await handle_spell_correction_response(
            update, context, session_manager, user_id
        )

        if corrected_word is None:
            # Still waiting for valid response
            return
        elif corrected_word == "":
            # User cancelled
            return
        else:
            # Process the corrected word
            word = corrected_word
    else:
        # New word - check spelling
        spell_result = spell_checker.check_spelling(word)

        if not spell_result.is_valid:
            if spell_result.suggestion:
                # Offer correction
                session_manager.set_pending_correction(
                    user_id,
                    word,
                    spell_result.suggestion
                )

                await update.message.reply_text(
                    f"🔍 Did you mean **{spell_result.suggestion}** instead of '{word}'?\n\n"
                    f"Reply with:\n"
                    f"• **yes** - to use '{spell_result.suggestion}'\n"
                    f"• **no** - to keep '{word}'\n"
                    f"• **cancel** - to cancel",
                    parse_mode='Markdown'
                )
                return
            else:
                # Invalid word with no suggestion
                # Check if it's a greeting
                if word.lower() in ['hi', 'hello', 'hey', 'bye', 'goodbye', 'ok', 'okay']:
                    await update.message.reply_text(
                        f"👋 Hello! I'm here to help you learn vocabulary.\n\n"
                        f"Send me any English word you'd like to learn, and I'll create a flashcard for you!\n\n"
                        f"For example: 'serendipity', 'eloquent', 'perseverance'"
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ '{word}' doesn't appear to be a valid vocabulary word.\n"
                        f"Please send an English word you'd like to learn."
                    )
                return

    # Process the word
    await process_word(
        word, update, context,
        anki_client, card_generator, session_manager
    )