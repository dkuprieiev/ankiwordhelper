"""Main entry point for Anki Telegram Bot."""

import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import settings
from anki_client import AnkiClient
from card_generator import CardGenerator
from utils import SessionManager, EnhancedSpellChecker
from handlers import (
    start_command,
    sync_command,
    stats_command,
    handle_text_message
)
from handlers.commands import help_command

logger = logging.getLogger(__name__)


def setup_bot_data(application: Application) -> None:
    """Initialize bot data with service instances."""
    application.bot_data['anki_client'] = AnkiClient()
    application.bot_data['card_generator'] = CardGenerator()
    application.bot_data['session_manager'] = SessionManager()
    application.bot_data['spell_checker'] = EnhancedSpellChecker()

    logger.info("Bot services initialized")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the bot."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again later."
        )


async def post_init(application: Application) -> None:
    """Post initialization hook."""
    # Check if Anki is available
    anki_client = application.bot_data['anki_client']
    if anki_client.is_running():
        logger.info("Anki is already running")
    else:
        logger.info("Anki is not running. Users will need to use /start")

    # Set bot commands
    await application.bot.set_my_commands([
        ("start", "Start Anki and initialize bot"),
        ("sync", "Sync Anki collection"),
        ("stats", "View deck statistics"),
        ("help", "Show help message")
    ])


async def shutdown(application: Application) -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down bot...")

    # Clear sessions
    session_manager = application.bot_data.get('session_manager')
    if session_manager:
        session_manager.clear_all_sessions()

    logger.info("Bot shutdown complete")


def main():
    """Start the bot."""
    logger.info("Starting Anki Telegram Bot")
    logger.info(f"Using Ollama model: {settings.ollama_model}")
    logger.info(f"Anki deck: {settings.anki_deck_name}")

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Initialize bot data
    setup_bot_data(application)

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("sync", sync_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    # Add error handler
    application.add_error_handler(error_handler)

    # Add lifecycle hooks
    application.post_init = post_init
    application.post_shutdown = shutdown

    # Start the bot
    logger.info("Bot starting polling...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)