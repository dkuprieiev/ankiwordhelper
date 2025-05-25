"""Session management for user interactions."""

import logging
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class UserSession:
    """User session data."""
    user_id: int
    pending_correction: Optional[Tuple[str, str]] = None
    last_activity: datetime = field(default_factory=datetime.now)
    generation_attempts: Dict[str, int] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manage user sessions and state."""

    def __init__(self, session_timeout_minutes: int = 30):
        self._sessions: Dict[int, UserSession] = {}
        self.timeout = timedelta(minutes=session_timeout_minutes)

    def get_or_create_session(self, user_id: int) -> UserSession:
        """Get existing session or create new one."""
        self._cleanup_expired_sessions()

        if user_id not in self._sessions:
            logger.info(f"Creating new session for user {user_id}")
            self._sessions[user_id] = UserSession(user_id=user_id)
        else:
            # Update last activity
            self._sessions[user_id].last_activity = datetime.now()

        return self._sessions[user_id]

    def get_pending_correction(self, user_id: int) -> Optional[Tuple[str, str]]:
        """Get pending spelling correction for user."""
        session = self.get_or_create_session(user_id)
        return session.pending_correction

    def set_pending_correction(self, user_id: int, original: str, suggestion: str):
        """Set pending spelling correction for user."""
        session = self.get_or_create_session(user_id)
        session.pending_correction = (original, suggestion)
        logger.info(f"Set pending correction for user {user_id}: {original} -> {suggestion}")

    def clear_pending_correction(self, user_id: int):
        """Clear pending spelling correction for user."""
        session = self.get_or_create_session(user_id)
        session.pending_correction = None
        logger.info(f"Cleared pending correction for user {user_id}")

    def increment_generation_attempts(self, user_id: int, word: str) -> int:
        """Track generation attempts for a word."""
        session = self.get_or_create_session(user_id)

        if word not in session.generation_attempts:
            session.generation_attempts[word] = 0

        session.generation_attempts[word] += 1
        return session.generation_attempts[word]

    def reset_generation_attempts(self, user_id: int, word: str):
        """Reset generation attempts for a word."""
        session = self.get_or_create_session(user_id)
        if word in session.generation_attempts:
            del session.generation_attempts[word]

    def set_user_preference(self, user_id: int, key: str, value: Any):
        """Set user preference."""
        session = self.get_or_create_session(user_id)
        session.preferences[key] = value
        logger.info(f"Set preference for user {user_id}: {key} = {value}")

    def get_user_preference(self, user_id: int, key: str, default: Any = None) -> Any:
        """Get user preference."""
        session = self.get_or_create_session(user_id)
        return session.preferences.get(key, default)

    def _cleanup_expired_sessions(self):
        """Remove expired sessions."""
        now = datetime.now()
        expired_users = []

        for user_id, session in self._sessions.items():
            if now - session.last_activity > self.timeout:
                expired_users.append(user_id)

        for user_id in expired_users:
            logger.info(f"Removing expired session for user {user_id}")
            del self._sessions[user_id]

    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        self._cleanup_expired_sessions()
        return len(self._sessions)

    def clear_all_sessions(self):
        """Clear all sessions (for testing or shutdown)."""
        logger.info(f"Clearing all {len(self._sessions)} sessions")
        self._sessions.clear()