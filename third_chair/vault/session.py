"""Session management for vault encryption.

Handles password caching and session lifecycle so users only need to
enter their password once per session.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import get_vault_config
from .crypto import KeyDerivation
from .exceptions import SessionExpiredError, VaultLockedError


@dataclass
class VaultSession:
    """Active vault session with cached derived key."""

    case_path: Path
    derived_key: bytes  # Raw 32-byte key for AES
    fernet_key: bytes  # Base64 encoded key for Fernet
    salt: bytes
    created_at: datetime = field(default_factory=datetime.now)
    last_access: datetime = field(default_factory=datetime.now)
    timeout_minutes: int = 30

    def is_expired(self) -> bool:
        """Check if session has timed out due to inactivity."""
        if self.timeout_minutes == 0:  # No timeout
            return False
        elapsed = datetime.now() - self.last_access
        return elapsed > timedelta(minutes=self.timeout_minutes)

    def touch(self) -> None:
        """Update last access time to prevent timeout."""
        self.last_access = datetime.now()

    def time_remaining(self) -> Optional[timedelta]:
        """Get time remaining before session expires."""
        if self.timeout_minutes == 0:
            return None
        elapsed = datetime.now() - self.last_access
        remaining = timedelta(minutes=self.timeout_minutes) - elapsed
        return max(remaining, timedelta(0))


class SessionManager:
    """
    Thread-safe session manager for vault operations.

    Maintains cached encryption keys in memory for active sessions.
    Supports both per-case and global (master password) sessions.
    """

    _instance: Optional["SessionManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize session manager (use get_instance() for singleton)."""
        self._sessions: dict[str, VaultSession] = {}  # case_path_str -> session
        self._session_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> "SessionManager":
        """Get singleton session manager instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.lock_all()
            cls._instance = None

    def _normalize_path(self, case_path: Path) -> str:
        """Normalize path for dictionary key."""
        return str(Path(case_path).resolve())

    def unlock_vault(
        self,
        case_path: Path,
        password: str,
        salt: bytes,
        timeout_minutes: Optional[int] = None,
    ) -> VaultSession:
        """
        Unlock a vault and create a session.

        Args:
            case_path: Path to the case directory
            password: Master password
            salt: Salt from vault.meta
            timeout_minutes: Session timeout (None = use config default)

        Returns:
            Active VaultSession
        """
        config = get_vault_config()
        timeout = timeout_minutes if timeout_minutes is not None else config.session_timeout_minutes

        # Derive keys from password
        derived_key = KeyDerivation.derive_key(password, salt)
        fernet_key = KeyDerivation.derive_fernet_key(password, salt)

        session = VaultSession(
            case_path=Path(case_path).resolve(),
            derived_key=derived_key,
            fernet_key=fernet_key,
            salt=salt,
            timeout_minutes=timeout,
        )

        path_key = self._normalize_path(case_path)

        with self._session_lock:
            self._sessions[path_key] = session

        return session

    def get_session(self, case_path: Path) -> Optional[VaultSession]:
        """
        Get active session for a case, checking expiry.

        Args:
            case_path: Path to case directory

        Returns:
            VaultSession if active and not expired, None otherwise
        """
        path_key = self._normalize_path(case_path)

        with self._session_lock:
            session = self._sessions.get(path_key)

            if session is None:
                return None

            if session.is_expired():
                # Clean up expired session
                del self._sessions[path_key]
                return None

            # Touch to extend timeout
            session.touch()
            return session

    def require_session(self, case_path: Path) -> VaultSession:
        """
        Get session or raise if locked/expired.

        Args:
            case_path: Path to case directory

        Returns:
            Active VaultSession

        Raises:
            VaultLockedError: If no active session
            SessionExpiredError: If session has expired
        """
        path_key = self._normalize_path(case_path)

        with self._session_lock:
            session = self._sessions.get(path_key)

            if session is None:
                raise VaultLockedError(f"Vault is locked: {case_path}")

            if session.is_expired():
                del self._sessions[path_key]
                raise SessionExpiredError()

            session.touch()
            return session

    def lock_vault(self, case_path: Path) -> bool:
        """
        Lock a vault by clearing its session.

        Args:
            case_path: Path to case directory

        Returns:
            True if session was cleared, False if no session existed
        """
        path_key = self._normalize_path(case_path)

        with self._session_lock:
            if path_key in self._sessions:
                # Securely clear the key from memory
                session = self._sessions[path_key]
                # Note: Python doesn't guarantee memory clearing, but we do our best
                del self._sessions[path_key]
                return True
            return False

    def lock_all(self) -> int:
        """
        Lock all vaults by clearing all sessions.

        Returns:
            Number of sessions cleared
        """
        with self._session_lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count

    def is_unlocked(self, case_path: Path) -> bool:
        """
        Check if a vault is unlocked (has active non-expired session).

        Args:
            case_path: Path to case directory

        Returns:
            True if unlocked
        """
        return self.get_session(case_path) is not None

    def get_active_sessions(self) -> list[VaultSession]:
        """
        Get list of all active (non-expired) sessions.

        Returns:
            List of active sessions
        """
        with self._session_lock:
            active = []
            expired_keys = []

            for key, session in self._sessions.items():
                if session.is_expired():
                    expired_keys.append(key)
                else:
                    active.append(session)

            # Clean up expired sessions
            for key in expired_keys:
                del self._sessions[key]

            return active

    def extend_session(self, case_path: Path, additional_minutes: int) -> bool:
        """
        Extend session timeout.

        Args:
            case_path: Path to case directory
            additional_minutes: Minutes to add to timeout

        Returns:
            True if session was extended
        """
        session = self.get_session(case_path)
        if session is None:
            return False

        with self._session_lock:
            session.timeout_minutes += additional_minutes
            session.touch()
            return True


# Module-level convenience functions


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    return SessionManager.get_instance()


def is_vault_unlocked(case_path: Path) -> bool:
    """Check if a vault is unlocked."""
    return get_session_manager().is_unlocked(case_path)


def get_vault_session(case_path: Path) -> Optional[VaultSession]:
    """Get active session for a case."""
    return get_session_manager().get_session(case_path)


def require_vault_session(case_path: Path) -> VaultSession:
    """Get session or raise VaultLockedError."""
    return get_session_manager().require_session(case_path)


def lock_vault(case_path: Path) -> bool:
    """Lock a vault."""
    return get_session_manager().lock_vault(case_path)


def lock_all_vaults() -> int:
    """Lock all vaults."""
    return get_session_manager().lock_all()
