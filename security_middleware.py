"""Security middleware for restricting bot access to authorized user."""

import logging
from functools import wraps
from typing import Optional, Callable
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Middleware to restrict bot access to a single authorized user."""

    def __init__(self, authorized_user_id: Optional[int] = None):
        """
        Initialize security middleware.

        Args:
            authorized_user_id: Telegram user ID of the authorized user.
                              If None, must be set later via set_authorized_user.
        """
        self._authorized_user_id = authorized_user_id
        self._unauthorized_attempts = {}  # Track unauthorized access attempts

    @property
    def authorized_user_id(self) -> Optional[int]:
        """Get authorized user ID."""
        return self._authorized_user_id

    def set_authorized_user(self, user_id: int):
        """Set or update the authorized user ID."""
        old_id = self._authorized_user_id
        self._authorized_user_id = user_id
        logger.info(f"Authorized user changed from {old_id} to {user_id}")

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        return self._authorized_user_id is not None and user_id == self._authorized_user_id

    def log_unauthorized_attempt(self, user_id: int, username: Optional[str], command: str):
        """Log unauthorized access attempt."""
        if user_id not in self._unauthorized_attempts:
            self._unauthorized_attempts[user_id] = []

        attempt = {
            'timestamp': datetime.now(),
            'username': username,
            'command': command
        }
        self._unauthorized_attempts[user_id].append(attempt)

        logger.warning(
            f"Unauthorized access attempt: user_id={user_id}, "
            f"username={username}, command={command}"
        )

    def get_unauthorized_attempts(self) -> dict:
        """Get all unauthorized access attempts."""
        return self._unauthorized_attempts.copy()

    def clear_unauthorized_attempts(self):
        """Clear unauthorized attempts log."""
        self._unauthorized_attempts.clear()


def require_authorization(security_middleware: SecurityMiddleware):
    """
    Decorator to require authorization for handlers.

    Args:
        security_middleware: Instance of SecurityMiddleware
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # Get user info
            user = update.effective_user
            if not user:
                return

            user_id = user.id
            username = user.username or user.first_name

            # Special handling for /start command with auth code
            if update.message and update.message.text and update.message.text.startswith('/start '):
                # Let the start command handler process the auth code
                return await func(update, context)

            # Check authorization
            if not security_middleware.is_authorized(user_id):
                # Log unauthorized attempt
                command = update.message.text if update.message else "unknown"
                security_middleware.log_unauthorized_attempt(user_id, username, command)

                # Send unauthorized message
                if update.message:
                    await update.message.reply_text(
                        "🚫 Unauthorized access.\n\n"
                        "This bot is private and restricted to authorized users only.\n"
                        "Your access attempt has been logged."
                    )

                    # If no authorized user is set yet, provide setup instructions
                    if security_middleware.authorized_user_id is None:
                        await update.message.reply_text(
                            "ℹ️ No authorized user configured yet.\n"
                            "Use /start <auth_code> to authenticate."
                        )

                return  # Don't execute the handler

            # User is authorized, execute handler
            return await func(update, context)

        return wrapper
    return decorator


# Additional security utilities

async def handle_auth_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    security_middleware: SecurityMiddleware,
    auth_code: str
):
    """
    Handle authentication with auth code.

    This should be called from the start command when an auth code is provided.
    """
    user = update.effective_user
    user_id = user.id

    # Check if auth code is valid (you should use a secure method here)
    # For production, use environment variable or secure storage
    expected_auth_code = context.bot_data.get('auth_code')

    if not expected_auth_code:
        await update.message.reply_text(
            "⚠️ Authentication not configured properly.\n"
            "Please set AUTH_CODE environment variable."
        )
        return False

    if auth_code != expected_auth_code:
        logger.warning(f"Invalid auth code attempt from user {user_id}")
        await update.message.reply_text("❌ Invalid authentication code.")
        return False

    # Set authorized user
    security_middleware.set_authorized_user(user_id)

    # Store in bot data for persistence
    context.bot_data['authorized_user_id'] = user_id

    await update.message.reply_text(
        f"✅ Authentication successful!\n"
        f"User ID {user_id} is now authorized to use this bot.\n\n"
        f"You can now use all bot commands."
    )

    logger.info(f"User {user_id} successfully authenticated")
    return True


def create_admin_commands(security_middleware: SecurityMiddleware):
    """Create admin command handlers."""

    async def show_security_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current security status (admin only)."""
        user_id = update.effective_user.id

        # Only the authorized user can see security status
        if not security_middleware.is_authorized(user_id):
            return

        auth_user = security_middleware.authorized_user_id
        attempts = security_middleware.get_unauthorized_attempts()

        status_msg = f"🔒 **Security Status**\n\n"
        status_msg += f"**Authorized User ID:** {auth_user}\n"
        status_msg += f"**Unauthorized Attempts:** {len(attempts)}\n"

        if attempts:
            status_msg += "\n**Recent Attempts:**\n"
            for user_id, user_attempts in list(attempts.items())[:5]:
                last_attempt = user_attempts[-1]
                status_msg += f"• User {user_id}: {len(user_attempts)} attempts\n"

        await update.message.reply_text(status_msg, parse_mode='Markdown')

    async def revoke_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Revoke current authorization (admin only)."""
        user_id = update.effective_user.id

        if not security_middleware.is_authorized(user_id):
            return

        # Confirm revocation
        await update.message.reply_text(
            "⚠️ This will revoke your access to the bot.\n"
            "You'll need to authenticate again with the auth code.\n\n"
            "Send /confirm_revoke to proceed."
        )

        # Store pending revocation
        context.user_data['pending_revoke'] = True

    async def confirm_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm access revocation."""
        user_id = update.effective_user.id

        if not security_middleware.is_authorized(user_id):
            return

        if not context.user_data.get('pending_revoke'):
            await update.message.reply_text("No pending revocation.")
            return

        # Clear authorization
        security_middleware.set_authorized_user(None)
        context.bot_data['authorized_user_id'] = None
        context.user_data['pending_revoke'] = False

        await update.message.reply_text(
            "✅ Access revoked successfully.\n"
            "Use /start <auth_code> to authenticate again."
        )

        logger.info(f"User {user_id} revoked their own access")

    return {
        'security_status': show_security_status,
        'revoke_access': revoke_access,
        'confirm_revoke': confirm_revoke
    }


# Import for datetime
from datetime import datetime