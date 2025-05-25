"""Command handlers for Telegram bot."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from anki_client import AnkiClient
from utils import SessionManager

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
/help - Show this help message

**Tips:**
• If I suggest a spelling correction, reply with 'yes', 'no', or 'cancel'
• Cards are validated for quality before adding
• Failed attempts are merged to create the best possible card

Send me a word to get started!"""

    await update.message.reply_text(help_text, parse_mode='Markdown')