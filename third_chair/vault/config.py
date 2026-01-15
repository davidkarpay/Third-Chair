"""Vault configuration for Third Chair encryption system."""

import os
from dataclasses import dataclass


@dataclass
class VaultConfig:
    """Configuration for vault encryption operations."""

    # Key derivation
    pbkdf2_iterations: int = 480_000  # OWASP 2023 recommendation
    salt_size: int = 32  # 256 bits
    key_size: int = 32  # 256 bits for AES-256

    # Streaming encryption
    chunk_size: int = 64 * 1024  # 64KB chunks
    streaming_threshold: int = 100 * 1024 * 1024  # 100MB - use streaming above this

    # Session management
    session_timeout_minutes: int = 30  # 0 = no timeout
    auto_lock_on_exit: bool = True

    # File naming
    encrypted_extension: str = ".enc"
    metadata_file: str = "vault.meta"

    # What to encrypt
    encrypt_case_json: bool = True
    encrypt_evidence: bool = True
    encrypt_reports: bool = False  # Reports can be regenerated
    encrypt_work_items: bool = False  # YAML work items

    # Directories to process
    encrypted_dirs: tuple = ("extracted",)
    skip_dirs: tuple = ("__pycache__", ".git", "reports", "work")

    @classmethod
    def from_env(cls) -> "VaultConfig":
        """
        Load configuration from environment variables.

        Environment variables:
            VAULT_SESSION_TIMEOUT: Session timeout in minutes (default: 30)
            VAULT_ENCRYPT_REPORTS: Whether to encrypt reports (default: false)
            VAULT_STREAMING_THRESHOLD: Size threshold for streaming (default: 100MB)
        """
        config = cls()

        if timeout := os.getenv("VAULT_SESSION_TIMEOUT"):
            config.session_timeout_minutes = int(timeout)

        if os.getenv("VAULT_ENCRYPT_REPORTS", "").lower() == "true":
            config.encrypt_reports = True

        if threshold := os.getenv("VAULT_STREAMING_THRESHOLD"):
            config.streaming_threshold = int(threshold)

        return config


# Global configuration instance
_config: VaultConfig | None = None


def get_vault_config() -> VaultConfig:
    """Get the global vault configuration."""
    global _config
    if _config is None:
        _config = VaultConfig.from_env()
    return _config


def set_vault_config(config: VaultConfig) -> None:
    """Set the global vault configuration."""
    global _config
    _config = config
