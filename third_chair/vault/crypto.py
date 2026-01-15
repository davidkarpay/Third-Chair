"""Core cryptographic primitives for vault encryption.

Uses the cryptography library for:
- PBKDF2-HMAC-SHA256 key derivation (480,000 iterations per OWASP 2023)
- Fernet (AES-128-CBC + HMAC-SHA256) for small files
- AES-256-GCM for streaming encryption of large files
"""

import base64
import os
from pathlib import Path
from typing import BinaryIO, Iterator

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import DecryptionError, EncryptionError

# Key derivation parameters (OWASP 2023 recommendations)
PBKDF2_ITERATIONS = 480_000
SALT_SIZE = 32  # 256 bits
KEY_SIZE = 32  # 256 bits for AES-256

# Streaming encryption parameters
CHUNK_SIZE = 64 * 1024  # 64KB chunks
NONCE_SIZE = 12  # 96 bits for AES-GCM
TAG_SIZE = 16  # 128-bit authentication tag

# Verification plaintext (encrypted to verify password)
VERIFICATION_PLAINTEXT = b"THIRD_CHAIR_VAULT_V1"


class KeyDerivation:
    """Derives encryption keys from master password using PBKDF2."""

    @staticmethod
    def generate_salt() -> bytes:
        """Generate cryptographically secure random salt."""
        return os.urandom(SALT_SIZE)

    @staticmethod
    def derive_key(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
        """
        Derive a 256-bit key from password using PBKDF2-HMAC-SHA256.

        Args:
            password: Master password
            salt: Random salt (should be stored with encrypted data)
            iterations: PBKDF2 iteration count

        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode("utf-8"))

    @staticmethod
    def derive_fernet_key(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
        """
        Derive a Fernet-compatible key (URL-safe base64 encoded).

        Fernet uses a specific key format, so we derive the raw key
        and encode it appropriately.

        Args:
            password: Master password
            salt: Random salt
            iterations: PBKDF2 iteration count

        Returns:
            URL-safe base64 encoded key for Fernet
        """
        raw_key = KeyDerivation.derive_key(password, salt, iterations)
        return base64.urlsafe_b64encode(raw_key)

    @staticmethod
    def create_verification_hash(password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
        """
        Create a verification hash to check password correctness.

        Encrypts a known plaintext with the derived key. On unlock,
        we decrypt and verify it matches the expected plaintext.

        Args:
            password: Master password
            salt: Salt used for key derivation
            iterations: PBKDF2 iteration count

        Returns:
            Encrypted verification value
        """
        fernet_key = KeyDerivation.derive_fernet_key(password, salt, iterations)
        fernet = Fernet(fernet_key)
        return fernet.encrypt(VERIFICATION_PLAINTEXT)

    @staticmethod
    def verify_password(
        password: str,
        salt: bytes,
        verification_hash: bytes,
        iterations: int = PBKDF2_ITERATIONS,
    ) -> bool:
        """
        Verify password by decrypting verification hash.

        Args:
            password: Password to verify
            salt: Salt from vault metadata
            verification_hash: Encrypted verification value
            iterations: PBKDF2 iteration count

        Returns:
            True if password is correct
        """
        try:
            fernet_key = KeyDerivation.derive_fernet_key(password, salt, iterations)
            fernet = Fernet(fernet_key)
            decrypted = fernet.decrypt(verification_hash)
            return decrypted == VERIFICATION_PLAINTEXT
        except InvalidToken:
            return False


class SmallFileEncryption:
    """
    Fernet-based encryption for small files (<100MB).

    Fernet provides authenticated encryption (AES-128-CBC + HMAC-SHA256).
    It's simpler to use than raw AES-GCM and handles IV generation internally.
    """

    def __init__(self, key: bytes):
        """
        Initialize with a Fernet-compatible key.

        Args:
            key: URL-safe base64 encoded 32-byte key
        """
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Encrypt data.

        Args:
            plaintext: Data to encrypt

        Returns:
            Encrypted data (includes IV and HMAC)
        """
        try:
            return self.fernet.encrypt(plaintext)
        except Exception as e:
            raise EncryptionError(f"Fernet encryption failed: {e}")

    def decrypt(self, ciphertext: bytes) -> bytes:
        """
        Decrypt data.

        Args:
            ciphertext: Encrypted data

        Returns:
            Decrypted plaintext
        """
        try:
            return self.fernet.decrypt(ciphertext)
        except InvalidToken:
            raise DecryptionError("Invalid ciphertext or wrong key")
        except Exception as e:
            raise DecryptionError(f"Fernet decryption failed: {e}")

    def encrypt_file(self, input_path: Path, output_path: Path) -> None:
        """
        Encrypt a file to disk.

        Args:
            input_path: Source file
            output_path: Destination for encrypted file
        """
        plaintext = input_path.read_bytes()
        ciphertext = self.encrypt(plaintext)
        output_path.write_bytes(ciphertext)

    def decrypt_file(self, input_path: Path, output_path: Path) -> None:
        """
        Decrypt a file to disk.

        Args:
            input_path: Encrypted file
            output_path: Destination for decrypted file
        """
        ciphertext = input_path.read_bytes()
        plaintext = self.decrypt(ciphertext)
        output_path.write_bytes(plaintext)


class StreamingEncryption:
    """
    AES-256-GCM streaming encryption for large files.

    Encrypts files in chunks to minimize memory usage for large video files.
    Each chunk has its own nonce and authentication tag.

    File format:
    [chunk_count (4 bytes)] [chunk1] [chunk2] ...
    Each chunk: [nonce (12 bytes)] [ciphertext] [tag (16 bytes)]
    """

    def __init__(self, key: bytes):
        """
        Initialize with a 256-bit key.

        Args:
            key: 32-byte encryption key (not base64 encoded)
        """
        if len(key) != KEY_SIZE:
            raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(key)}")
        self.aesgcm = AESGCM(key)

    def _encrypt_chunk(self, chunk: bytes) -> bytes:
        """Encrypt a single chunk with random nonce."""
        nonce = os.urandom(NONCE_SIZE)
        ciphertext = self.aesgcm.encrypt(nonce, chunk, None)
        # ciphertext includes tag appended by AESGCM
        return nonce + ciphertext

    def _decrypt_chunk(self, encrypted_chunk: bytes) -> bytes:
        """Decrypt a single chunk."""
        nonce = encrypted_chunk[:NONCE_SIZE]
        ciphertext = encrypted_chunk[NONCE_SIZE:]
        try:
            return self.aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            raise DecryptionError("Chunk decryption failed - corrupted or wrong key")

    def encrypt_stream(self, input_path: Path, output_path: Path) -> None:
        """
        Encrypt a large file in streaming fashion.

        Args:
            input_path: Source file
            output_path: Destination for encrypted file
        """
        file_size = input_path.stat().st_size
        chunk_count = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        with open(input_path, "rb") as infile, open(output_path, "wb") as outfile:
            # Write chunk count header
            outfile.write(chunk_count.to_bytes(4, "big"))

            while True:
                chunk = infile.read(CHUNK_SIZE)
                if not chunk:
                    break
                encrypted_chunk = self._encrypt_chunk(chunk)
                # Write chunk length then chunk data
                outfile.write(len(encrypted_chunk).to_bytes(4, "big"))
                outfile.write(encrypted_chunk)

    def decrypt_stream(self, input_path: Path, output_path: Path) -> None:
        """
        Decrypt a large file in streaming fashion.

        Args:
            input_path: Encrypted file
            output_path: Destination for decrypted file
        """
        with open(input_path, "rb") as infile, open(output_path, "wb") as outfile:
            # Read chunk count
            chunk_count_bytes = infile.read(4)
            if len(chunk_count_bytes) < 4:
                raise DecryptionError("Invalid encrypted file format")
            chunk_count = int.from_bytes(chunk_count_bytes, "big")

            for _ in range(chunk_count):
                # Read chunk length
                length_bytes = infile.read(4)
                if len(length_bytes) < 4:
                    raise DecryptionError("Unexpected end of file")
                chunk_length = int.from_bytes(length_bytes, "big")

                # Read and decrypt chunk
                encrypted_chunk = infile.read(chunk_length)
                if len(encrypted_chunk) < chunk_length:
                    raise DecryptionError("Unexpected end of file")

                plaintext = self._decrypt_chunk(encrypted_chunk)
                outfile.write(plaintext)

    def decrypt_chunks(self, input_path: Path) -> Iterator[bytes]:
        """
        Iterate over decrypted chunks (for streaming reads).

        Args:
            input_path: Encrypted file

        Yields:
            Decrypted chunks
        """
        with open(input_path, "rb") as infile:
            chunk_count_bytes = infile.read(4)
            if len(chunk_count_bytes) < 4:
                raise DecryptionError("Invalid encrypted file format")
            chunk_count = int.from_bytes(chunk_count_bytes, "big")

            for _ in range(chunk_count):
                length_bytes = infile.read(4)
                if len(length_bytes) < 4:
                    raise DecryptionError("Unexpected end of file")
                chunk_length = int.from_bytes(length_bytes, "big")

                encrypted_chunk = infile.read(chunk_length)
                if len(encrypted_chunk) < chunk_length:
                    raise DecryptionError("Unexpected end of file")

                yield self._decrypt_chunk(encrypted_chunk)


def get_encryptor(key: bytes, file_size: int, streaming_threshold: int = 100 * 1024 * 1024):
    """
    Get appropriate encryptor based on file size.

    Args:
        key: Raw 32-byte key
        file_size: Size of file to encrypt
        streaming_threshold: Size above which to use streaming (default 100MB)

    Returns:
        SmallFileEncryption or StreamingEncryption instance
    """
    if file_size >= streaming_threshold:
        return StreamingEncryption(key)
    else:
        fernet_key = base64.urlsafe_b64encode(key)
        return SmallFileEncryption(fernet_key)
