"""Vault exceptions for Third Chair encryption system."""


class VaultError(Exception):
    """Base exception for vault operations."""

    pass


class VaultLockedError(VaultError):
    """Raised when attempting to access a locked vault."""

    def __init__(self, message: str = "Vault is locked. Unlock with password first."):
        super().__init__(message)


class InvalidPasswordError(VaultError):
    """Raised when password verification fails."""

    def __init__(self, message: str = "Invalid password."):
        super().__init__(message)


class VaultNotFoundError(VaultError):
    """Raised when vault.meta file is not found."""

    def __init__(self, path: str = ""):
        message = f"Vault not found: {path}" if path else "Vault not found."
        super().__init__(message)


class VaultAlreadyExistsError(VaultError):
    """Raised when trying to initialize vault on already encrypted case."""

    def __init__(self, message: str = "Case is already encrypted."):
        super().__init__(message)


class VaultCorruptedError(VaultError):
    """Raised when vault metadata or files are corrupted."""

    def __init__(self, message: str = "Vault data is corrupted."):
        super().__init__(message)


class DecryptionError(VaultError):
    """Raised when decryption fails."""

    def __init__(self, message: str = "Failed to decrypt file."):
        super().__init__(message)


class EncryptionError(VaultError):
    """Raised when encryption fails."""

    def __init__(self, message: str = "Failed to encrypt file."):
        super().__init__(message)


class SessionExpiredError(VaultError):
    """Raised when vault session has timed out."""

    def __init__(self, message: str = "Session has expired. Please unlock again."):
        super().__init__(message)
