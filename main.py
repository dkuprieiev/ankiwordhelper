"""Main entry point for Anki Telegram Bot with single-user security."""

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
from security_middleware import (
    SecurityMiddleware,
    require_authorization,
    handle_auth_command,
    create_admin_commands
)
from handlers import (
    sync_command,
    stats_command,
    handle_text_message
)
from handlers.commands import help_command

logger = logging.getLogger(__name__)


def setup_bot_data(application: Application) -> None:
    """Initialize bot data with service instances."""
    # Initialize security middleware
    security_middleware = SecurityMiddleware(settings.authorized_user_id)

    # Store services in bot data
    application.bot_data['security_middleware'] = security_middleware
    application.bot_data['anki_client'] = AnkiClient()
    application.bot_data['card_generator'] = CardGenerator()
    application.bot_data['session_manager'] = SessionManager()
    application.bot_data['spell_checker'] = EnhancedSpellChecker()
    application.bot_data['auth_code'] = settings.auth_code

    # Restore authorized user if previously set
    if settings.authorized_user_id:
        security_middleware.set_authorized_user(settings.authorized_user_id)
        logger.info(f"Restored authorized user: {settings.authorized_user_id}")

    logger.info("Bot services initialized with security middleware")


async def secure_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with authentication support."""
    user_id = update.effective_user.id
    security_middleware: SecurityMiddleware = context.bot_data['security_middleware']

    # Check if auth code is provided
    if context.args and len(context.args) > 0:
        auth_code = context.args[0]
        logger.info(f"User {user_id} attempting authentication with code")

        # Handle authentication
        success = await handle_auth_command(update, context, security_middleware, auth_code)

        if success:
            # Continue with normal start command
            await start_anki_bot(update, context)
        return

    # Check if user is authorized
    if not security_middleware.is_authorized(user_id):
        logger.warning(f"Unauthorized start attempt from user {user_id}")

        await update.message.reply_text(
            "🚫 **Unauthorized Access**\n\n"
            "This bot is private and requires authentication.\n"
            "If you have an authentication code, use:\n"
            "`/start YOUR_AUTH_CODE`",
            parse_mode='Markdown'
        )
        return

    # User is authorized, proceed with normal start
    await start_anki_bot(update, context)


async def start_anki_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the Anki bot for authorized user."""
    anki_client: AnkiClient = context.bot_data['anki_client']

    # Check Anki status
    if anki_client.is_running():
        await update.message.reply_text(
            "✅ Anki is already running!\n\n"
            "Send me any English word and I'll create a flashcard for you.\n"
            "Commands:\n"
            "/sync - Sync your Anki collection\n"
            "/stats - View deck statistics\n"
            "/security - View security status\n"
            "/help - Show help message"
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


# Create secured versions of all handlers
def create_secured_handlers(security_middleware: SecurityMiddleware):
    """Create all handlers with security decorators."""

    # Decorate existing handlers
    secure_sync = require_authorization(security_middleware)(sync_command)
    secure_stats = require_authorization(security_middleware)(stats_command)
    secure_help = require_authorization(security_middleware)(help_command)
    secure_message = require_authorization(security_middleware)(handle_text_message)

    # Create admin commands
    admin_commands = create_admin_commands(security_middleware)
    secure_security_status = require_authorization(security_middleware)(admin_commands['security_status'])
    secure_revoke = require_authorization(security_middleware)(admin_commands['revoke_access'])
    secure_confirm_revoke = require_authorization(security_middleware)(admin_commands['confirm_revoke'])

    return {
        'sync': secure_sync,
        'stats': secure_stats,
        'help': secure_help,
        'message': secure_message,
        'security': secure_security_status,
        'revoke': secure_revoke,
        'confirm_revoke': secure_confirm_revoke
    }


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
        ("start", "Authenticate and start bot"),
        ("sync", "Sync Anki collection"),
        ("stats", "View deck statistics"),
        ("security", "View security status"),
        ("help", "Show help message")
    ])

    # Log security status
    security_middleware = application.bot_data['security_middleware']
    if security_middleware.authorized_user_id:
        logger.info(f"Bot started with authorized user: {security_middleware.authorized_user_id}")
    else:
        logger.warning("Bot started without authorized user. Authentication required.")


async def shutdown(application: Application) -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down bot...")

    # Save security state
    security_middleware = application.bot_data.get('security_middleware')
    if security_middleware and settings.enable_security_logs:
        attempts = security_middleware.get_unauthorized_attempts()
        if attempts:
            logger.info(f"Unauthorized access attempts during session: {len(attempts)}")

    # Clear sessions
    session_manager = application.bot_data.get('session_manager')
    if session_manager:
        session_manager.clear_all_sessions()

    logger.info("Bot shutdown complete")


def main():
    """Start the bot with security."""
    logger.info("Starting Secure Anki Telegram Bot")
    logger.info(f"Security enabled: Auth code required")
    logger.info(f"Using Ollama model: {settings.ollama_model}")
    logger.info(f"Anki deck: {settings.anki_deck_name}")

    # Create application
    application = Application.builder().token(settings.telegram_bot_token).build()

    # Initialize bot data including security
    setup_bot_data(application)

    # Get security middleware
    security_middleware = application.bot_data['security_middleware']

    # Create secured handlers
    secured_handlers = create_secured_handlers(security_middleware)

    # Add handlers
    # Start command doesn't use decorator as it handles auth
    application.add_handler(CommandHandler("start", secure_start_command))

    # All other handlers are secured
    application.add_handler(CommandHandler("sync", secured_handlers['sync']))
    application.add_handler(CommandHandler("stats", secured_handlers['stats']))
    application.add_handler(CommandHandler("security", secured_handlers['security']))
    application.add_handler(CommandHandler("help", secured_handlers['help']))
    application.add_handler(CommandHandler("revoke", secured_handlers['revoke']))
    application.add_handler(CommandHandler("confirm_revoke", secured_handlers['confirm_revoke']))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, secured_handlers['message'])
    )

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