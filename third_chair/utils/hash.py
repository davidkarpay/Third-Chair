"""File hashing utilities for integrity verification.

Provides SHA-256 hashing for evidence files to ensure:
- Chain of custody verification
- File integrity validation
- Duplicate detection
"""

import hashlib
from pathlib import Path
from typing import Optional, BinaryIO


# Default chunk size for reading large files (8 MB)
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024


def hash_file(
    file_path: Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """
    Calculate the hash of a file.

    Args:
        file_path: Path to the file
        algorithm: Hash algorithm (sha256, sha1, md5)
        chunk_size: Size of chunks to read

    Returns:
        Hexadecimal hash string
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    hasher = hashlib.new(algorithm)

    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def hash_file_sha256(file_path: Path) -> str:
    """
    Calculate SHA-256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        SHA-256 hash as hex string
    """
    return hash_file(file_path, algorithm="sha256")


def hash_stream(
    stream: BinaryIO,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """
    Calculate hash from a binary stream.

    Args:
        stream: Binary file-like object
        algorithm: Hash algorithm
        chunk_size: Size of chunks to read

    Returns:
        Hexadecimal hash string
    """
    hasher = hashlib.new(algorithm)

    while chunk := stream.read(chunk_size):
        hasher.update(chunk)

    return hasher.hexdigest()


def hash_bytes(data: bytes, algorithm: str = "sha256") -> str:
    """
    Calculate hash of bytes.

    Args:
        data: Bytes to hash
        algorithm: Hash algorithm

    Returns:
        Hexadecimal hash string
    """
    hasher = hashlib.new(algorithm)
    hasher.update(data)
    return hasher.hexdigest()


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """
    Calculate hash of a string.

    Args:
        text: String to hash
        algorithm: Hash algorithm

    Returns:
        Hexadecimal hash string
    """
    return hash_bytes(text.encode("utf-8"), algorithm)


def verify_file_hash(
    file_path: Path,
    expected_hash: str,
    algorithm: str = "sha256",
) -> bool:
    """
    Verify a file matches an expected hash.

    Args:
        file_path: Path to the file
        expected_hash: Expected hash value
        algorithm: Hash algorithm

    Returns:
        True if hash matches, False otherwise
    """
    try:
        actual_hash = hash_file(file_path, algorithm=algorithm)
        return actual_hash.lower() == expected_hash.lower()
    except Exception:
        return False


def generate_evidence_id(
    file_path: Path,
    prefix: str = "EV",
) -> str:
    """
    Generate an evidence ID based on file hash.

    Creates a short, unique identifier for evidence tracking.

    Args:
        file_path: Path to the evidence file
        prefix: Prefix for the ID

    Returns:
        Evidence ID (e.g., "EV-A1B2C3D4")
    """
    file_hash = hash_file_sha256(file_path)
    # Use first 8 characters of hash
    short_hash = file_hash[:8].upper()
    return f"{prefix}-{short_hash}"


def find_duplicates(file_paths: list[Path]) -> dict[str, list[Path]]:
    """
    Find duplicate files by hash.

    Args:
        file_paths: List of file paths to check

    Returns:
        Dictionary mapping hash to list of files with that hash
    """
    hash_to_files: dict[str, list[Path]] = {}

    for path in file_paths:
        try:
            file_hash = hash_file_sha256(path)
            if file_hash not in hash_to_files:
                hash_to_files[file_hash] = []
            hash_to_files[file_hash].append(path)
        except Exception:
            continue  # Skip files that can't be hashed

    # Filter to only include hashes with multiple files
    duplicates = {
        h: files for h, files in hash_to_files.items()
        if len(files) > 1
    }

    return duplicates


class FileIntegrityTracker:
    """Tracks file integrity for a collection of files."""

    def __init__(self):
        """Initialize tracker."""
        self.hashes: dict[Path, str] = {}

    def add_file(self, path: Path) -> str:
        """
        Add a file to the tracker.

        Args:
            path: Path to the file

        Returns:
            SHA-256 hash of the file
        """
        path = Path(path).resolve()
        file_hash = hash_file_sha256(path)
        self.hashes[path] = file_hash
        return file_hash

    def add_files(self, paths: list[Path]) -> dict[Path, str]:
        """
        Add multiple files to the tracker.

        Args:
            paths: List of file paths

        Returns:
            Dictionary mapping paths to hashes
        """
        results = {}
        for path in paths:
            try:
                results[path] = self.add_file(path)
            except Exception:
                continue
        return results

    def verify(self, path: Path) -> bool:
        """
        Verify a file hasn't changed.

        Args:
            path: Path to verify

        Returns:
            True if file matches stored hash
        """
        path = Path(path).resolve()

        if path not in self.hashes:
            return False

        return verify_file_hash(path, self.hashes[path])

    def verify_all(self) -> dict[Path, bool]:
        """
        Verify all tracked files.

        Returns:
            Dictionary mapping paths to verification results
        """
        return {path: self.verify(path) for path in self.hashes}

    def get_hash(self, path: Path) -> Optional[str]:
        """Get stored hash for a file."""
        path = Path(path).resolve()
        return self.hashes.get(path)

    def to_dict(self) -> dict[str, str]:
        """Export hashes as dictionary."""
        return {str(path): hash_val for path, hash_val in self.hashes.items()}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "FileIntegrityTracker":
        """Create tracker from dictionary."""
        tracker = cls()
        tracker.hashes = {Path(path): hash_val for path, hash_val in data.items()}
        return tracker
