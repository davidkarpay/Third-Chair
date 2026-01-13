"""Utility modules for Third Chair.

Provides common utilities:
- Logging configuration
- Place name preservation
- File hashing and integrity
"""

from .hash import (
    FileIntegrityTracker,
    find_duplicates,
    generate_evidence_id,
    hash_bytes,
    hash_file,
    hash_file_sha256,
    hash_stream,
    hash_string,
    verify_file_hash,
)
from .logging import (
    ProgressLogger,
    console,
    get_logger,
    setup_logging,
)
from .places import (
    PlaceNamePreserver,
    get_place_preserver,
    protect_places,
    restore_places,
)


__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "console",
    "ProgressLogger",
    # Places
    "PlaceNamePreserver",
    "get_place_preserver",
    "protect_places",
    "restore_places",
    # Hashing
    "hash_file",
    "hash_file_sha256",
    "hash_stream",
    "hash_bytes",
    "hash_string",
    "verify_file_hash",
    "generate_evidence_id",
    "find_duplicates",
    "FileIntegrityTracker",
]
