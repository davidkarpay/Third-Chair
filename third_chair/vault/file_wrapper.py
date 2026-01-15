"""Transparent file access wrapper for encrypted files.

Provides Path-like objects that transparently decrypt files on access,
allowing existing code to work with encrypted vaults with minimal changes.
"""

import io
import os
import tempfile
from pathlib import Path
from typing import BinaryIO, Optional, Union

from .exceptions import VaultLockedError
from .session import VaultSession, get_session_manager
from .vault_manager import VaultManager, is_vault_encrypted


class EncryptedPath:
    """
    Path-like object that transparently handles encrypted files.

    Wraps a Path to an encrypted file and provides transparent decryption.
    Compatible with code expecting Path objects through __fspath__().

    Usage:
        enc_path = EncryptedPath(encrypted_file, session)
        data = enc_path.read_bytes()  # Decrypted automatically
        str(enc_path)  # Returns path to temp decrypted file (for FFmpeg)

    Note:
        Temp files are cleaned up when the EncryptedPath is deleted or
        when cleanup() is called explicitly.
    """

    def __init__(
        self,
        encrypted_path: Path,
        session: VaultSession,
        vault_manager: Optional[VaultManager] = None,
    ):
        """
        Initialize encrypted path wrapper.

        Args:
            encrypted_path: Path to the encrypted file
            session: Active vault session with decryption keys
            vault_manager: VaultManager instance (created if not provided)
        """
        self._encrypted_path = Path(encrypted_path)
        self._session = session
        self._vault_manager = vault_manager or VaultManager(
            encrypted_path.parent.parent  # Assumes extracted/file.enc structure
        )
        self._temp_file: Optional[Path] = None
        self._decrypted_data: Optional[bytes] = None

    def __fspath__(self) -> str:
        """
        Return path to decrypted file for os.path operations.

        This creates a temp file if not already created.
        Required for compatibility with os.path and subprocess calls.
        """
        return str(self._get_decrypted_path())

    def __str__(self) -> str:
        """Return path to decrypted file."""
        return self.__fspath__()

    def __repr__(self) -> str:
        """Return representation."""
        return f"EncryptedPath({self._encrypted_path})"

    def _get_decrypted_path(self) -> Path:
        """Get path to decrypted file, creating temp if needed."""
        if self._temp_file is None:
            self._temp_file = self._decrypt_to_temp()
        return self._temp_file

    def _decrypt_to_temp(self) -> Path:
        """Decrypt to a temporary file."""
        # Get original extension
        original_name = self._vault_manager.get_decrypted_path(self._encrypted_path).name
        suffix = Path(original_name).suffix

        # Create temp file with same extension
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix="tc_vault_")
        os.close(fd)
        temp_path = Path(temp_path)

        # Decrypt to temp file
        self._vault_manager.decrypt_file(
            self._encrypted_path,
            temp_path,
            self._session,
        )

        return temp_path

    def read_bytes(self) -> bytes:
        """
        Read decrypted content as bytes.

        Caches the decrypted data for subsequent reads.
        """
        if self._decrypted_data is None:
            self._decrypted_data = self._vault_manager.decrypt_file_to_memory(
                self._encrypted_path,
                self._session,
            )
        return self._decrypted_data

    def read_text(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        """Read decrypted content as text."""
        return self.read_bytes().decode(encoding, errors)

    def open(self, mode: str = "rb") -> BinaryIO:
        """
        Open for reading (decrypted).

        Only read modes are supported.
        """
        if "w" in mode or "a" in mode:
            raise ValueError("EncryptedPath only supports read modes")

        data = self.read_bytes()
        return io.BytesIO(data)

    def exists(self) -> bool:
        """Check if encrypted file exists."""
        return self._encrypted_path.exists()

    def stat(self):
        """Get file stats of decrypted file."""
        if self._temp_file:
            return self._temp_file.stat()
        # Return encrypted file stats if not decrypted
        return self._encrypted_path.stat()

    @property
    def name(self) -> str:
        """Get original filename (without .enc)."""
        return self._vault_manager.get_decrypted_path(self._encrypted_path).name

    @property
    def stem(self) -> str:
        """Get original stem."""
        return Path(self.name).stem

    @property
    def suffix(self) -> str:
        """Get original suffix."""
        return Path(self.name).suffix

    @property
    def parent(self) -> Path:
        """Get parent directory."""
        return self._encrypted_path.parent

    def cleanup(self) -> None:
        """Remove temp file if created."""
        if self._temp_file and self._temp_file.exists():
            try:
                self._temp_file.unlink()
            except OSError:
                pass  # Best effort cleanup
            self._temp_file = None
        self._decrypted_data = None

    def __del__(self):
        """Cleanup temp file on deletion."""
        self.cleanup()


class VaultFileAccessor:
    """
    Context manager for accessing files in an encrypted vault.

    Handles session management and temp file cleanup automatically.

    Usage:
        with VaultFileAccessor(case_dir) as accessor:
            # Load case data
            case_data = accessor.load_json(case_dir / "case.json.enc")

            # Get path to evidence file (decrypts if needed)
            video_path = accessor.get_file_path(evidence.file_path)
            # video_path is either original Path or EncryptedPath

        # All temp files cleaned up on exit
    """

    def __init__(
        self,
        case_dir: Path,
        session: Optional[VaultSession] = None,
        auto_unlock: bool = False,
        password: Optional[str] = None,
    ):
        """
        Initialize file accessor.

        Args:
            case_dir: Path to case directory
            session: Existing session (fetched from manager if not provided)
            auto_unlock: If True and no session, prompt for password
            password: Password to use for auto_unlock
        """
        self.case_dir = Path(case_dir).resolve()
        self._session = session
        self._auto_unlock = auto_unlock
        self._password = password
        self._vault_manager: Optional[VaultManager] = None
        self._temp_paths: list[EncryptedPath] = []

    def __enter__(self) -> "VaultFileAccessor":
        """Enter context, ensuring vault is unlocked."""
        if is_vault_encrypted(self.case_dir):
            self._vault_manager = VaultManager(self.case_dir)

            if self._session is None:
                self._session = get_session_manager().get_session(self.case_dir)

            if self._session is None:
                if self._auto_unlock and self._password:
                    self._session = self._vault_manager.unlock(self._password)
                else:
                    raise VaultLockedError(f"Vault is locked: {self.case_dir}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context, cleanup temp files."""
        self._cleanup_temp_files()
        return False

    def _cleanup_temp_files(self) -> None:
        """Clean up all created temp files."""
        for enc_path in self._temp_paths:
            enc_path.cleanup()
        self._temp_paths.clear()

    @property
    def is_encrypted(self) -> bool:
        """Check if vault is encrypted."""
        return self._vault_manager is not None

    def get_file_path(self, original_path: Path) -> Union[Path, EncryptedPath]:
        """
        Get path to a file, handling encryption transparently.

        For unencrypted vaults, returns the original path.
        For encrypted vaults, returns EncryptedPath that decrypts on access.

        Args:
            original_path: Original file path

        Returns:
            Path or EncryptedPath
        """
        if not self.is_encrypted:
            return original_path

        # Check if encrypted version exists
        encrypted_path = self._vault_manager.get_encrypted_path(original_path)

        if encrypted_path.exists():
            enc_path = EncryptedPath(
                encrypted_path,
                self._session,
                self._vault_manager,
            )
            self._temp_paths.append(enc_path)
            return enc_path
        elif original_path.exists():
            # File wasn't encrypted
            return original_path
        else:
            # Try the encrypted path
            enc_path = EncryptedPath(
                encrypted_path,
                self._session,
                self._vault_manager,
            )
            self._temp_paths.append(enc_path)
            return enc_path

    def load_json(self, file_path: Path) -> dict:
        """
        Load JSON from a file, decrypting if needed.

        Args:
            file_path: Path to JSON file (with or without .enc)

        Returns:
            Parsed JSON data
        """
        if not self.is_encrypted:
            import json

            return json.loads(file_path.read_text(encoding="utf-8"))

        # Check for .enc version
        if not str(file_path).endswith(".enc"):
            encrypted_path = self._vault_manager.get_encrypted_path(file_path)
        else:
            encrypted_path = file_path

        if encrypted_path.exists():
            return self._vault_manager.decrypt_json(encrypted_path, self._session)
        else:
            # Fall back to unencrypted
            import json

            return json.loads(file_path.read_text(encoding="utf-8"))

    def save_json(self, data: dict, file_path: Path) -> Path:
        """
        Save JSON to a file, encrypting if vault exists.

        Args:
            data: Data to serialize
            file_path: Target path

        Returns:
            Path where data was saved
        """
        if not self.is_encrypted:
            import json

            file_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return file_path

        encrypted_path = self._vault_manager.get_encrypted_path(file_path)
        return self._vault_manager.encrypt_json(data, encrypted_path, self._session)


def get_evidence_path(
    evidence_file_path: Path,
    case_dir: Path,
    session: Optional[VaultSession] = None,
) -> Union[Path, EncryptedPath]:
    """
    Convenience function to get path to an evidence file.

    Args:
        evidence_file_path: Original evidence file path
        case_dir: Case directory
        session: Vault session (fetched from manager if not provided)

    Returns:
        Path or EncryptedPath for the file
    """
    if not is_vault_encrypted(case_dir):
        return evidence_file_path

    if session is None:
        session = get_session_manager().get_session(case_dir)

    if session is None:
        raise VaultLockedError(f"Vault is locked: {case_dir}")

    vm = VaultManager(case_dir)
    encrypted_path = vm.get_encrypted_path(evidence_file_path)

    if encrypted_path.exists():
        return EncryptedPath(encrypted_path, session, vm)

    return evidence_file_path
