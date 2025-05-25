"""Command handlers for Telegram bot."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from anki_client import AnkiClient
from utils import SessionManager
from config import settings

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    logger.info(f"Start command from user {user_id}")

    # Get or create anki client from context
    anki_client: AnkiClient = context.bot_data['anki_client']

    # Check Anki status
    if anki_client.is_running():
        await update.message.reply_text(
            "✅ Anki is already running!\n\n"
            "Send me any English word and I'll create a flashcard for you.\n"
            "Commands:\n"
            "/sync - Sync your Anki collection\n"
            "/stats - View deck statistics\n"
            "/debug - Show debug information\n"
            "/help - Show this help message"
        )
    else:
        await update.message.reply_text("🚀 Starting Anki...")

        if anki_client.start():
            await update.message.reply_text(
                "✅ Anki started successfully!\n\n"
                "Send me any English word and I'll create a flashcard for you."
            )
        else:
            await update.message.reply_text(
                "❌ Failed to start Anki!\n"
                "Please make sure Anki is installed and try again."
            )


async def sync_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sync command."""
    user_id = update.effective_user.id
    logger.info(f"Sync command from user {user_id}")

    anki_client: AnkiClient = context.bot_data['anki_client']

    if not anki_client.ensure_running():
        await update.message.reply_text("❌ Anki is not running! Use /start first.")
        return

    await update.message.reply_text("🔄 Syncing Anki collection...")

    if anki_client.sync():
        await update.message.reply_text("✅ Sync completed successfully!")
    else:
        await update.message.reply_text(
            "❌ Sync failed!\n"
            "Please check your Anki sync settings."
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    user_id = update.effective_user.id
    logger.info(f"Stats command from user {user_id}")

    anki_client: AnkiClient = context.bot_data['anki_client']
    session_manager: SessionManager = context.bot_data['session_manager']

    if not anki_client.ensure_running():
        await update.message.reply_text("❌ Anki is not running! Use /start first.")
        return

    # Get deck stats
    stats = anki_client.get_deck_stats()

    if "error" in stats:
        await update.message.reply_text(f"❌ Failed to get stats: {stats['error']}")
        return

    # Format stats message
    deck_name = anki_client.deck_name
    active_sessions = session_manager.get_active_sessions_count()

    message = f"""📊 **Anki Statistics**

**Deck:** {deck_name}
**Active bot sessions:** {active_sessions}

Send me more words to add to your collection!"""

    await update.message.reply_text(message, parse_mode='Markdown')


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /debug command to show current configuration."""
    await update.message.reply_text("Debug command received!")  # ADD THIS
    user_id = update.effective_user.id
    logger.info(f"Debug command from user {user_id}")

    anki_client: AnkiClient = context.bot_data['anki_client']

    # Initialize variables
    available_decks = []
    test_notes = []
    test_query = f'deck:"{anki_client.deck_name}"'

    # Test deck search
    if anki_client.ensure_running():
        # Try to get deck info
        deck_names_result = anki_client._make_request("deckNames")
        available_decks = deck_names_result.get("result", []) if "result" in deck_names_result else []

        # Try a simple search in the configured deck
        test_notes = anki_client.find_notes(test_query)

    # Get current configuration
    debug_info = f"""🔧 **Debug Information**

**Anki Configuration:**
- URL: `{anki_client.url}`
- Deck Name: `{anki_client.deck_name}`
- Deck Name (repr): `{repr(anki_client.deck_name)}`
- Model Name: `{anki_client.model_name}`
- Anki Running: {anki_client.is_running()}

**Available Decks:**
{chr(10).join(f"- {deck}" for deck in available_decks[:10]) if available_decks else "Failed to retrieve decks"}

**Test Search Results:**
- Query: `{test_query}`
- Notes found: {len(test_notes)}

**Bot Configuration:**
- Max Generation Attempts: {settings.max_generation_attempts}
- Ollama Model: {settings.ollama_model}
- Log Level: {settings.log_level}

**Environment Check:**
- ANKI_DECK_NAME from env: `{repr(settings.anki_deck_name)}`

Send me a word to test the duplicate detection!"""

    await update.message.reply_text(debug_info, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """🤖 **Anki Vocabulary Bot Help**

**How to use:**
1. Simply send me any English word
2. I'll check the spelling and create a flashcard
3. The card will be automatically added to Anki

**Features:**
• Spell checking with suggestions
• Ukrainian translations
• IPA pronunciation (British & American)
• Example sentences
• Automatic quality validation
• Auto-sync after adding cards

**Commands:**
/start - Start Anki and initialize bot
/sync - Manually sync Anki collection
/stats - View deck statistics
/debug - Show debug information
/help - Show this help message

**Tips:**
• If I suggest a spelling correction, reply with 'yes', 'no', or 'cancel'
• Cards are validated for quality before adding
• Failed attempts are merged to create the best possible card

Send me a word to get started!"""

    await update.message.reply_text(help_text, parse_mode='Markdown')