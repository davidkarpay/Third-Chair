"""Vault manager for high-level encryption operations.

Handles vault initialization, password verification, and file encryption/decryption.
"""

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import VaultConfig, get_vault_config
from .crypto import (
    KeyDerivation,
    SmallFileEncryption,
    StreamingEncryption,
    get_encryptor,
)
from .exceptions import (
    DecryptionError,
    EncryptionError,
    InvalidPasswordError,
    VaultAlreadyExistsError,
    VaultCorruptedError,
    VaultNotFoundError,
)
from .session import VaultSession, get_session_manager


@dataclass
class VaultMetadata:
    """
    Metadata stored in vault.meta file.

    This file is NOT encrypted - it contains only:
    - Salt for key derivation
    - Algorithm parameters
    - Verification hash (encrypted known plaintext)
    """

    version: int = 1
    algorithm: str = "AES-256-GCM"
    key_derivation: str = "PBKDF2-HMAC-SHA256"
    iterations: int = 480_000
    salt: bytes = field(default_factory=bytes)
    verification_hash: bytes = field(default_factory=bytes)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "algorithm": self.algorithm,
            "key_derivation": self.key_derivation,
            "iterations": self.iterations,
            "salt": base64.b64encode(self.salt).decode("ascii"),
            "verification_hash": base64.b64encode(self.verification_hash).decode("ascii"),
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VaultMetadata":
        """Create from dictionary."""
        return cls(
            version=data.get("version", 1),
            algorithm=data.get("algorithm", "AES-256-GCM"),
            key_derivation=data.get("key_derivation", "PBKDF2-HMAC-SHA256"),
            iterations=data.get("iterations", 480_000),
            salt=base64.b64decode(data["salt"]),
            verification_hash=base64.b64decode(data["verification_hash"]),
            created_at=data.get("created_at", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "VaultMetadata":
        """Deserialize from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            raise VaultCorruptedError(f"Invalid vault metadata: {e}")


class VaultManager:
    """
    Manages encryption/decryption operations for a case vault.

    Usage:
        vm = VaultManager(case_dir)

        # Check if encrypted
        if vm.is_encrypted:
            vm.unlock(password)
        else:
            vm.initialize(password)  # Encrypt for first time

        # Load/save encrypted files
        data = vm.decrypt_file(path)
        vm.encrypt_file(data, path)
    """

    def __init__(self, case_dir: Path, config: Optional[VaultConfig] = None):
        """
        Initialize vault manager for a case directory.

        Args:
            case_dir: Path to case directory
            config: Vault configuration (uses global if not provided)
        """
        self.case_dir = Path(case_dir).resolve()
        self.config = config or get_vault_config()
        self._metadata: Optional[VaultMetadata] = None

    @property
    def metadata_path(self) -> Path:
        """Path to vault.meta file."""
        return self.case_dir / self.config.metadata_file

    @property
    def is_encrypted(self) -> bool:
        """Check if this case has an encrypted vault."""
        return self.metadata_path.exists()

    @property
    def metadata(self) -> VaultMetadata:
        """Load and cache vault metadata."""
        if self._metadata is None:
            self._metadata = self.load_metadata()
        return self._metadata

    def load_metadata(self) -> VaultMetadata:
        """Load vault metadata from disk."""
        if not self.metadata_path.exists():
            raise VaultNotFoundError(str(self.case_dir))
        try:
            content = self.metadata_path.read_text(encoding="utf-8")
            return VaultMetadata.from_json(content)
        except Exception as e:
            raise VaultCorruptedError(f"Failed to load vault metadata: {e}")

    def save_metadata(self, metadata: VaultMetadata) -> None:
        """Save vault metadata to disk."""
        self.metadata_path.write_text(metadata.to_json(), encoding="utf-8")
        self._metadata = metadata

    def initialize(self, password: str) -> VaultMetadata:
        """
        Initialize a new vault (encrypt existing case).

        Args:
            password: Master password

        Returns:
            VaultMetadata

        Raises:
            VaultAlreadyExistsError: If already encrypted
            ValueError: If password is too weak
        """
        if self.is_encrypted:
            raise VaultAlreadyExistsError()

        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        # Generate salt and verification hash
        salt = KeyDerivation.generate_salt()
        verification_hash = KeyDerivation.create_verification_hash(
            password, salt, self.config.pbkdf2_iterations
        )

        metadata = VaultMetadata(
            iterations=self.config.pbkdf2_iterations,
            salt=salt,
            verification_hash=verification_hash,
            created_at=datetime.now().isoformat(),
        )

        # Save metadata first
        self.save_metadata(metadata)

        # Create session
        session = get_session_manager().unlock_vault(
            self.case_dir, password, salt
        )

        return metadata

    def verify_password(self, password: str) -> bool:
        """
        Verify password against stored verification hash.

        Args:
            password: Password to verify

        Returns:
            True if password is correct
        """
        if not self.is_encrypted:
            return False

        return KeyDerivation.verify_password(
            password,
            self.metadata.salt,
            self.metadata.verification_hash,
            self.metadata.iterations,
        )

    def unlock(self, password: str, timeout_minutes: Optional[int] = None) -> VaultSession:
        """
        Unlock vault with password.

        Args:
            password: Master password
            timeout_minutes: Session timeout (None = use config)

        Returns:
            VaultSession

        Raises:
            VaultNotFoundError: If not encrypted
            InvalidPasswordError: If wrong password
        """
        if not self.is_encrypted:
            raise VaultNotFoundError(str(self.case_dir))

        if not self.verify_password(password):
            raise InvalidPasswordError()

        return get_session_manager().unlock_vault(
            self.case_dir,
            password,
            self.metadata.salt,
            timeout_minutes,
        )

    def get_encrypted_path(self, original_path: Path) -> Path:
        """
        Get the encrypted path for a file.

        Args:
            original_path: Original file path

        Returns:
            Path with .enc extension
        """
        return original_path.with_suffix(original_path.suffix + self.config.encrypted_extension)

    def get_decrypted_path(self, encrypted_path: Path) -> Path:
        """
        Get the original path from an encrypted path.

        Args:
            encrypted_path: Path with .enc extension

        Returns:
            Original path without .enc
        """
        name = encrypted_path.name
        if name.endswith(self.config.encrypted_extension):
            name = name[: -len(self.config.encrypted_extension)]
        return encrypted_path.parent / name

    def encrypt_file(
        self,
        source_path: Path,
        dest_path: Optional[Path] = None,
        session: Optional[VaultSession] = None,
    ) -> Path:
        """
        Encrypt a file.

        Args:
            source_path: File to encrypt
            dest_path: Output path (default: source + .enc)
            session: Vault session (uses active session if not provided)

        Returns:
            Path to encrypted file
        """
        if session is None:
            session = get_session_manager().require_session(self.case_dir)

        source_path = Path(source_path)
        if dest_path is None:
            dest_path = self.get_encrypted_path(source_path)

        file_size = source_path.stat().st_size

        if file_size >= self.config.streaming_threshold:
            # Large file - use streaming encryption
            encryptor = StreamingEncryption(session.derived_key)
            encryptor.encrypt_stream(source_path, dest_path)
        else:
            # Small file - use Fernet
            encryptor = SmallFileEncryption(session.fernet_key)
            encryptor.encrypt_file(source_path, dest_path)

        return dest_path

    def decrypt_file(
        self,
        encrypted_path: Path,
        dest_path: Optional[Path] = None,
        session: Optional[VaultSession] = None,
    ) -> Path:
        """
        Decrypt a file to disk.

        Args:
            encrypted_path: Encrypted file path
            dest_path: Output path (default: remove .enc)
            session: Vault session

        Returns:
            Path to decrypted file
        """
        if session is None:
            session = get_session_manager().require_session(self.case_dir)

        encrypted_path = Path(encrypted_path)
        if dest_path is None:
            dest_path = self.get_decrypted_path(encrypted_path)

        # Check file size to determine encryption method
        file_size = encrypted_path.stat().st_size

        # Heuristic: streaming encrypted files have a header
        # Try streaming first for large files
        if file_size >= self.config.streaming_threshold:
            try:
                decryptor = StreamingEncryption(session.derived_key)
                decryptor.decrypt_stream(encrypted_path, dest_path)
                return dest_path
            except DecryptionError:
                pass  # Try Fernet

        # Try Fernet decryption
        decryptor = SmallFileEncryption(session.fernet_key)
        decryptor.decrypt_file(encrypted_path, dest_path)
        return dest_path

    def decrypt_file_to_memory(
        self,
        encrypted_path: Path,
        session: Optional[VaultSession] = None,
    ) -> bytes:
        """
        Decrypt a file to memory (for small files).

        Args:
            encrypted_path: Encrypted file path
            session: Vault session

        Returns:
            Decrypted content
        """
        if session is None:
            session = get_session_manager().require_session(self.case_dir)

        ciphertext = encrypted_path.read_bytes()
        decryptor = SmallFileEncryption(session.fernet_key)
        return decryptor.decrypt(ciphertext)

    def encrypt_data(
        self,
        data: bytes,
        session: Optional[VaultSession] = None,
    ) -> bytes:
        """
        Encrypt data in memory.

        Args:
            data: Data to encrypt
            session: Vault session

        Returns:
            Encrypted data
        """
        if session is None:
            session = get_session_manager().require_session(self.case_dir)

        encryptor = SmallFileEncryption(session.fernet_key)
        return encryptor.encrypt(data)

    def decrypt_data(
        self,
        encrypted_data: bytes,
        session: Optional[VaultSession] = None,
    ) -> bytes:
        """
        Decrypt data in memory.

        Args:
            encrypted_data: Encrypted data
            session: Vault session

        Returns:
            Decrypted data
        """
        if session is None:
            session = get_session_manager().require_session(self.case_dir)

        decryptor = SmallFileEncryption(session.fernet_key)
        return decryptor.decrypt(encrypted_data)

    def encrypt_json(
        self,
        data: dict[str, Any],
        dest_path: Path,
        session: Optional[VaultSession] = None,
    ) -> Path:
        """
        Encrypt JSON data to file.

        Args:
            data: Dictionary to serialize and encrypt
            dest_path: Output path
            session: Vault session

        Returns:
            Path to encrypted file
        """
        json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        encrypted = self.encrypt_data(json_bytes, session)
        dest_path.write_bytes(encrypted)
        return dest_path

    def decrypt_json(
        self,
        encrypted_path: Path,
        session: Optional[VaultSession] = None,
    ) -> dict[str, Any]:
        """
        Decrypt JSON file.

        Args:
            encrypted_path: Encrypted JSON file
            session: Vault session

        Returns:
            Deserialized dictionary
        """
        encrypted_data = encrypted_path.read_bytes()
        decrypted = self.decrypt_data(encrypted_data, session)
        return json.loads(decrypted.decode("utf-8"))

    def should_encrypt_file(self, file_path: Path) -> bool:
        """
        Check if a file should be encrypted based on configuration.

        Args:
            file_path: Path to check

        Returns:
            True if file should be encrypted
        """
        rel_path = file_path.relative_to(self.case_dir) if file_path.is_absolute() else file_path

        # Skip certain directories
        for skip_dir in self.config.skip_dirs:
            if rel_path.parts and rel_path.parts[0] == skip_dir.rstrip("/"):
                return False

        # Check if in encrypted directory
        for enc_dir in self.config.encrypted_dirs:
            if rel_path.parts and rel_path.parts[0] == enc_dir:
                return True

        # case.json is always encrypted
        if rel_path.name == "case.json":
            return self.config.encrypt_case_json

        return False


def is_vault_encrypted(case_dir: Path) -> bool:
    """Check if a case directory has an encrypted vault."""
    config = get_vault_config()
    return (Path(case_dir) / config.metadata_file).exists()


def get_vault_manager(case_dir: Path) -> VaultManager:
    """Get a vault manager for a case directory."""
    return VaultManager(case_dir)
