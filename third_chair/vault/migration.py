"""Migration tools for vault encryption.

Provides commands to:
- Encrypt existing unencrypted cases
- Export decrypted copies for backup
- Verify vault integrity
- Rotate (change) passwords
"""

import shutil
from pathlib import Path
from typing import Callable, Optional

from .config import get_vault_config
from .exceptions import VaultAlreadyExistsError, VaultNotFoundError
from .session import get_session_manager
from .vault_manager import VaultManager, is_vault_encrypted


def encrypt_existing_case(
    case_dir: Path,
    password: str,
    show_progress: bool = True,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> dict:
    """
    Encrypt an existing unencrypted case.

    Creates vault.meta, encrypts case.json and files in extracted/.
    Original unencrypted files are removed after successful encryption.

    Args:
        case_dir: Path to case directory
        password: Master password
        show_progress: Whether to print progress
        progress_callback: Optional callback(message, current, total)

    Returns:
        Dict with encryption statistics

    Raises:
        VaultAlreadyExistsError: If already encrypted
        ValueError: If password is too weak
        FileNotFoundError: If case.json not found
    """
    case_dir = Path(case_dir).resolve()
    config = get_vault_config()

    # Validate
    if is_vault_encrypted(case_dir):
        raise VaultAlreadyExistsError()

    case_json = case_dir / "case.json"
    if not case_json.exists():
        raise FileNotFoundError(f"case.json not found in {case_dir}")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    # Initialize vault (creates vault.meta and session)
    vm = VaultManager(case_dir)
    vm.initialize(password)

    stats = {
        "files_encrypted": 0,
        "bytes_encrypted": 0,
        "files_skipped": 0,
        "errors": [],
    }

    # Collect files to encrypt
    files_to_encrypt = []

    # Always encrypt case.json
    if config.encrypt_case_json and case_json.exists():
        files_to_encrypt.append(case_json)

    # Collect files from encrypted directories
    for enc_dir in config.encrypted_dirs:
        dir_path = case_dir / enc_dir
        if dir_path.exists() and dir_path.is_dir():
            for file_path in dir_path.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith(config.encrypted_extension):
                    files_to_encrypt.append(file_path)

    total_files = len(files_to_encrypt)

    def report_progress(message: str, current: int):
        if show_progress:
            print(f"  [{current}/{total_files}] {message}")
        if progress_callback:
            progress_callback(message, current, total_files)

    # Encrypt files
    for i, file_path in enumerate(files_to_encrypt, 1):
        try:
            report_progress(f"Encrypting {file_path.name}", i)

            encrypted_path = vm.encrypt_file(file_path)
            stats["bytes_encrypted"] += file_path.stat().st_size
            stats["files_encrypted"] += 1

            # Remove original file after successful encryption
            file_path.unlink()

        except Exception as e:
            stats["errors"].append(f"{file_path.name}: {e}")
            stats["files_skipped"] += 1

    if show_progress:
        print(f"\nEncrypted {stats['files_encrypted']} files ({stats['bytes_encrypted']:,} bytes)")
        if stats["errors"]:
            print(f"Errors: {len(stats['errors'])}")
            for error in stats["errors"][:5]:
                print(f"  - {error}")

    return stats


def decrypt_case_for_export(
    case_dir: Path,
    password: str,
    output_dir: Path,
    show_progress: bool = True,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> dict:
    """
    Export a decrypted copy of an encrypted case.

    Creates a new directory with fully decrypted files.
    Original encrypted vault remains unchanged.

    Args:
        case_dir: Path to encrypted case
        password: Master password
        output_dir: Where to export decrypted files
        show_progress: Whether to print progress
        progress_callback: Optional callback(message, current, total)

    Returns:
        Dict with export statistics

    Raises:
        VaultNotFoundError: If not encrypted
        InvalidPasswordError: If wrong password
    """
    case_dir = Path(case_dir).resolve()
    output_dir = Path(output_dir).resolve()
    config = get_vault_config()

    if not is_vault_encrypted(case_dir):
        raise VaultNotFoundError(str(case_dir))

    # Unlock vault
    vm = VaultManager(case_dir)
    vm.unlock(password)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "files_decrypted": 0,
        "bytes_decrypted": 0,
        "files_copied": 0,
        "errors": [],
    }

    # Collect all files to process
    all_files = []

    for item in case_dir.rglob("*"):
        if item.is_file():
            # Skip vault metadata
            if item.name == config.metadata_file:
                continue
            all_files.append(item)

    total_files = len(all_files)

    def report_progress(message: str, current: int):
        if show_progress:
            print(f"  [{current}/{total_files}] {message}")
        if progress_callback:
            progress_callback(message, current, total_files)

    # Process files
    for i, file_path in enumerate(all_files, 1):
        try:
            rel_path = file_path.relative_to(case_dir)

            if file_path.name.endswith(config.encrypted_extension):
                # Decrypt
                report_progress(f"Decrypting {file_path.name}", i)

                # Remove .enc from output path
                out_name = file_path.name[: -len(config.encrypted_extension)]
                out_path = output_dir / rel_path.parent / out_name
                out_path.parent.mkdir(parents=True, exist_ok=True)

                vm.decrypt_file(file_path, out_path)
                stats["files_decrypted"] += 1
                stats["bytes_decrypted"] += out_path.stat().st_size

            else:
                # Copy unencrypted files
                report_progress(f"Copying {file_path.name}", i)

                out_path = output_dir / rel_path
                out_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, out_path)
                stats["files_copied"] += 1

        except Exception as e:
            stats["errors"].append(f"{file_path.name}: {e}")

    if show_progress:
        print(f"\nDecrypted {stats['files_decrypted']} files")
        print(f"Copied {stats['files_copied']} unencrypted files")
        if stats["errors"]:
            print(f"Errors: {len(stats['errors'])}")

    return stats


def verify_vault_integrity(
    case_dir: Path,
    password: str,
    show_progress: bool = True,
) -> dict:
    """
    Verify all encrypted files can be decrypted.

    Does not write any files - only verifies decryption works.

    Args:
        case_dir: Path to encrypted case
        password: Master password
        show_progress: Whether to print progress

    Returns:
        Dict with verification results
    """
    case_dir = Path(case_dir).resolve()
    config = get_vault_config()

    if not is_vault_encrypted(case_dir):
        raise VaultNotFoundError(str(case_dir))

    vm = VaultManager(case_dir)
    vm.unlock(password)

    stats = {
        "files_verified": 0,
        "files_failed": 0,
        "errors": [],
    }

    # Find all encrypted files
    encrypted_files = list(case_dir.rglob(f"*{config.encrypted_extension}"))
    total = len(encrypted_files)

    for i, enc_file in enumerate(encrypted_files, 1):
        if show_progress:
            print(f"  [{i}/{total}] Verifying {enc_file.name}")

        try:
            # Try to decrypt (to memory for small files)
            if enc_file.stat().st_size < config.streaming_threshold:
                vm.decrypt_file_to_memory(enc_file)
            else:
                # For large files, decrypt first chunk only
                from .crypto import StreamingEncryption

                session = get_session_manager().require_session(case_dir)
                decryptor = StreamingEncryption(session.derived_key)

                # Just get first chunk to verify
                for chunk in decryptor.decrypt_chunks(enc_file):
                    break  # Only verify first chunk

            stats["files_verified"] += 1

        except Exception as e:
            stats["files_failed"] += 1
            stats["errors"].append(f"{enc_file.name}: {e}")

    if show_progress:
        print(f"\nVerified: {stats['files_verified']}")
        print(f"Failed: {stats['files_failed']}")

    return stats


def rotate_password(
    case_dir: Path,
    old_password: str,
    new_password: str,
    show_progress: bool = True,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> dict:
    """
    Change vault password.

    Re-encrypts all files with new key derived from new password.

    Args:
        case_dir: Path to encrypted case
        old_password: Current password
        new_password: New password
        show_progress: Whether to print progress
        progress_callback: Optional callback

    Returns:
        Dict with rotation statistics
    """
    case_dir = Path(case_dir).resolve()
    config = get_vault_config()

    if not is_vault_encrypted(case_dir):
        raise VaultNotFoundError(str(case_dir))

    if len(new_password) < 8:
        raise ValueError("New password must be at least 8 characters")

    # Unlock with old password
    vm = VaultManager(case_dir)
    old_session = vm.unlock(old_password)

    stats = {
        "files_rotated": 0,
        "errors": [],
    }

    # Find all encrypted files
    encrypted_files = list(case_dir.rglob(f"*{config.encrypted_extension}"))
    total = len(encrypted_files)

    def report_progress(message: str, current: int):
        if show_progress:
            print(f"  [{current}/{total}] {message}")
        if progress_callback:
            progress_callback(message, current, total)

    # Create new vault metadata with new password
    from .crypto import KeyDerivation

    new_salt = KeyDerivation.generate_salt()
    new_verification = KeyDerivation.create_verification_hash(
        new_password, new_salt, config.pbkdf2_iterations
    )

    # Derive new keys
    new_derived_key = KeyDerivation.derive_key(new_password, new_salt)
    new_fernet_key = KeyDerivation.derive_fernet_key(new_password, new_salt)

    # Re-encrypt each file
    for i, enc_file in enumerate(encrypted_files, 1):
        try:
            report_progress(f"Re-encrypting {enc_file.name}", i)

            # Decrypt with old key
            decrypted = vm.decrypt_file_to_memory(enc_file, old_session)

            # Create new encryptor with new key
            from .crypto import SmallFileEncryption

            new_encryptor = SmallFileEncryption(new_fernet_key)

            # Re-encrypt
            encrypted = new_encryptor.encrypt(decrypted)
            enc_file.write_bytes(encrypted)

            stats["files_rotated"] += 1

        except Exception as e:
            stats["errors"].append(f"{enc_file.name}: {e}")

    # Update vault metadata with new salt and verification hash
    metadata = vm.metadata
    metadata.salt = new_salt
    metadata.verification_hash = new_verification
    vm.save_metadata(metadata)

    # Clear old session and create new one
    get_session_manager().lock_vault(case_dir)
    vm.unlock(new_password)

    if show_progress:
        print(f"\nRotated {stats['files_rotated']} files")
        if stats["errors"]:
            print(f"Errors: {len(stats['errors'])}")

    return stats


def remove_encryption(
    case_dir: Path,
    password: str,
    show_progress: bool = True,
) -> dict:
    """
    Remove encryption from a case (decrypt in place).

    Decrypts all files and removes vault.meta.

    Args:
        case_dir: Path to encrypted case
        password: Master password
        show_progress: Whether to print progress

    Returns:
        Dict with results
    """
    case_dir = Path(case_dir).resolve()
    config = get_vault_config()

    if not is_vault_encrypted(case_dir):
        raise VaultNotFoundError(str(case_dir))

    vm = VaultManager(case_dir)
    vm.unlock(password)

    stats = {
        "files_decrypted": 0,
        "errors": [],
    }

    # Find all encrypted files
    encrypted_files = list(case_dir.rglob(f"*{config.encrypted_extension}"))
    total = len(encrypted_files)

    for i, enc_file in enumerate(encrypted_files, 1):
        if show_progress:
            print(f"  [{i}/{total}] Decrypting {enc_file.name}")

        try:
            # Get output path (remove .enc)
            out_path = vm.get_decrypted_path(enc_file)

            # Decrypt
            vm.decrypt_file(enc_file, out_path)

            # Remove encrypted file
            enc_file.unlink()

            stats["files_decrypted"] += 1

        except Exception as e:
            stats["errors"].append(f"{enc_file.name}: {e}")

    # Remove vault metadata
    metadata_path = case_dir / config.metadata_file
    if metadata_path.exists():
        metadata_path.unlink()

    # Clear session
    get_session_manager().lock_vault(case_dir)

    if show_progress:
        print(f"\nDecrypted {stats['files_decrypted']} files")
        print("Vault removed.")

    return stats
