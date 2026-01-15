"""Vault encryption module for Third Chair.

Provides AES-256 encryption for case directories to protect
sensitive legal discovery data from unauthorized access.

Usage:
    # Check if case is encrypted
    from third_chair.vault import is_vault_encrypted
    if is_vault_encrypted(case_dir):
        # Unlock vault
        vm = VaultManager(case_dir)
        vm.unlock(password)

    # Encrypt existing case
    from third_chair.vault import encrypt_existing_case
    encrypt_existing_case(case_dir, password)

    # Access encrypted files transparently
    from third_chair.vault import VaultFileAccessor
    with VaultFileAccessor(case_dir) as accessor:
        data = accessor.load_json(case_dir / "case.json.enc")
"""

# Exceptions
from .exceptions import (
    DecryptionError,
    EncryptionError,
    InvalidPasswordError,
    SessionExpiredError,
    VaultAlreadyExistsError,
    VaultCorruptedError,
    VaultError,
    VaultLockedError,
    VaultNotFoundError,
)

# Configuration
from .config import (
    VaultConfig,
    get_vault_config,
    set_vault_config,
)

# Session management
from .session import (
    VaultSession,
    SessionManager,
    get_session_manager,
    get_vault_session,
    is_vault_unlocked,
    lock_all_vaults,
    lock_vault,
    require_vault_session,
)

# Vault operations
from .vault_manager import (
    VaultManager,
    VaultMetadata,
    get_vault_manager,
    is_vault_encrypted,
)

# File access
from .file_wrapper import (
    EncryptedPath,
    VaultFileAccessor,
    get_evidence_path,
)

# Migration tools
from .migration import (
    decrypt_case_for_export,
    encrypt_existing_case,
    remove_encryption,
    rotate_password,
    verify_vault_integrity,
)

__all__ = [
    # Exceptions
    "VaultError",
    "VaultLockedError",
    "InvalidPasswordError",
    "VaultNotFoundError",
    "VaultAlreadyExistsError",
    "VaultCorruptedError",
    "DecryptionError",
    "EncryptionError",
    "SessionExpiredError",
    # Configuration
    "VaultConfig",
    "get_vault_config",
    "set_vault_config",
    # Session
    "VaultSession",
    "SessionManager",
    "get_session_manager",
    "get_vault_session",
    "require_vault_session",
    "is_vault_unlocked",
    "lock_vault",
    "lock_all_vaults",
    # Vault manager
    "VaultManager",
    "VaultMetadata",
    "get_vault_manager",
    "is_vault_encrypted",
    # File access
    "EncryptedPath",
    "VaultFileAccessor",
    "get_evidence_path",
    # Migration
    "encrypt_existing_case",
    "decrypt_case_for_export",
    "verify_vault_integrity",
    "rotate_password",
    "remove_encryption",
]
