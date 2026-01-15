"""Unit tests for the vault encryption module."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest


class TestKeyDerivation:
    """Tests for PBKDF2 key derivation."""

    def test_generate_salt(self):
        """Test salt generation produces correct length."""
        from third_chair.vault.crypto import KeyDerivation

        salt = KeyDerivation.generate_salt()
        assert len(salt) == 32  # 256 bits

    def test_generate_salt_unique(self):
        """Test each salt generation is unique."""
        from third_chair.vault.crypto import KeyDerivation

        salts = [KeyDerivation.generate_salt() for _ in range(10)]
        assert len(set(salts)) == 10  # All unique

    def test_derive_key(self):
        """Test key derivation produces consistent results."""
        from third_chair.vault.crypto import KeyDerivation

        password = "test_password_123"
        salt = KeyDerivation.generate_salt()

        key1 = KeyDerivation.derive_key(password, salt)
        key2 = KeyDerivation.derive_key(password, salt)

        assert key1 == key2
        assert len(key1) == 32  # 256 bits

    def test_derive_key_different_passwords(self):
        """Test different passwords produce different keys."""
        from third_chair.vault.crypto import KeyDerivation

        salt = KeyDerivation.generate_salt()

        key1 = KeyDerivation.derive_key("password1", salt)
        key2 = KeyDerivation.derive_key("password2", salt)

        assert key1 != key2

    def test_derive_fernet_key(self):
        """Test Fernet key derivation produces valid base64."""
        from third_chair.vault.crypto import KeyDerivation
        import base64

        salt = KeyDerivation.generate_salt()
        fernet_key = KeyDerivation.derive_fernet_key("test_password", salt)

        # Should be valid base64
        decoded = base64.urlsafe_b64decode(fernet_key)
        assert len(decoded) == 32  # Fernet requires 32 bytes

    def test_verification_hash(self):
        """Test verification hash creation and validation."""
        from third_chair.vault.crypto import KeyDerivation

        password = "secure_password_123"
        salt = KeyDerivation.generate_salt()
        iterations = 10_000  # Fewer for faster tests

        hash1 = KeyDerivation.create_verification_hash(password, salt, iterations)

        # Verify with correct password
        assert KeyDerivation.verify_password(password, salt, hash1, iterations)

        # Verify fails with wrong password
        assert not KeyDerivation.verify_password("wrong_password", salt, hash1, iterations)


class TestSmallFileEncryption:
    """Tests for Fernet-based small file encryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypting and decrypting returns original data."""
        from third_chair.vault.crypto import SmallFileEncryption, KeyDerivation

        salt = KeyDerivation.generate_salt()
        key = KeyDerivation.derive_fernet_key("test_password", salt)
        encryptor = SmallFileEncryption(key)

        original_data = b"This is some test data to encrypt."

        encrypted = encryptor.encrypt(original_data)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == original_data
        assert encrypted != original_data  # Should be different

    def test_encrypt_decrypt_file(self, tmp_path):
        """Test file encryption and decryption."""
        from third_chair.vault.crypto import SmallFileEncryption, KeyDerivation

        salt = KeyDerivation.generate_salt()
        key = KeyDerivation.derive_fernet_key("test_password", salt)
        encryptor = SmallFileEncryption(key)

        # Create source file
        source = tmp_path / "original.txt"
        source.write_bytes(b"Test file content for encryption.")

        # Encrypt
        encrypted = tmp_path / "encrypted.enc"
        encryptor.encrypt_file(source, encrypted)

        assert encrypted.exists()
        assert encrypted.read_bytes() != source.read_bytes()

        # Decrypt
        decrypted = tmp_path / "decrypted.txt"
        encryptor.decrypt_file(encrypted, decrypted)

        assert decrypted.read_bytes() == source.read_bytes()


class TestStreamingEncryption:
    """Tests for AES-256-GCM streaming encryption."""

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        """Test streaming encryption/decryption roundtrip via files."""
        from third_chair.vault.crypto import StreamingEncryption, KeyDerivation

        salt = KeyDerivation.generate_salt()
        key = KeyDerivation.derive_key("test_password", salt)

        original_data = b"Test data " * 1000  # 10KB

        # Create source file
        source = tmp_path / "source.bin"
        source.write_bytes(original_data)

        encrypted = tmp_path / "encrypted.enc"
        decrypted = tmp_path / "decrypted.bin"

        # Encrypt
        encryptor = StreamingEncryption(key)
        encryptor.encrypt_stream(source, encrypted)

        # Decrypt
        decryptor = StreamingEncryption(key)
        decryptor.decrypt_stream(encrypted, decrypted)

        assert decrypted.read_bytes() == original_data

    def test_encrypt_decrypt_file(self, tmp_path):
        """Test large file streaming encryption."""
        from third_chair.vault.crypto import StreamingEncryption, KeyDerivation

        salt = KeyDerivation.generate_salt()
        key = KeyDerivation.derive_key("test_password", salt)

        # Create a test file (100KB)
        source = tmp_path / "large_file.bin"
        source.write_bytes(b"X" * 100_000)

        encrypted = tmp_path / "large_file.enc"
        decrypted = tmp_path / "large_file_dec.bin"

        # Encrypt
        encryptor = StreamingEncryption(key)
        encryptor.encrypt_stream(source, encrypted)

        assert encrypted.exists()
        assert encrypted.read_bytes() != source.read_bytes()

        # Decrypt
        decryptor = StreamingEncryption(key)
        decryptor.decrypt_stream(encrypted, decrypted)

        assert decrypted.read_bytes() == source.read_bytes()


class TestVaultSession:
    """Tests for vault session management."""

    def test_session_creation(self, tmp_path):
        """Test creating a vault session."""
        from third_chair.vault.session import VaultSession

        session = VaultSession(
            case_path=tmp_path,
            derived_key=b"0" * 32,
            fernet_key=b"0" * 32,
            salt=b"0" * 32,
            timeout_minutes=30,
        )

        assert session.case_path == tmp_path
        assert not session.is_expired()

    def test_session_expiry(self, tmp_path):
        """Test session expiry detection."""
        from third_chair.vault.session import VaultSession

        session = VaultSession(
            case_path=tmp_path,
            derived_key=b"0" * 32,
            fernet_key=b"0" * 32,
            salt=b"0" * 32,
            timeout_minutes=1,
        )

        # Should not be expired initially
        assert not session.is_expired()

        # Artificially age the session
        session.last_access = datetime.now() - timedelta(minutes=2)
        assert session.is_expired()

    def test_session_no_timeout(self, tmp_path):
        """Test session with no timeout."""
        from third_chair.vault.session import VaultSession

        session = VaultSession(
            case_path=tmp_path,
            derived_key=b"0" * 32,
            fernet_key=b"0" * 32,
            salt=b"0" * 32,
            timeout_minutes=0,  # No timeout
        )

        # Age the session
        session.last_access = datetime.now() - timedelta(hours=24)
        assert not session.is_expired()

    def test_session_touch(self, tmp_path):
        """Test session touch extends timeout."""
        from third_chair.vault.session import VaultSession

        session = VaultSession(
            case_path=tmp_path,
            derived_key=b"0" * 32,
            fernet_key=b"0" * 32,
            salt=b"0" * 32,
            timeout_minutes=30,
        )

        original_access = session.last_access
        session.touch()

        assert session.last_access >= original_access


class TestSessionManager:
    """Tests for the session manager."""

    def test_unlock_vault(self, tmp_path):
        """Test unlocking a vault creates a session."""
        from third_chair.vault.session import SessionManager

        manager = SessionManager()
        salt = b"0" * 32

        session = manager.unlock_vault(tmp_path, "password", salt)

        assert session is not None
        assert manager.is_unlocked(tmp_path)

    def test_get_session(self, tmp_path):
        """Test getting an existing session."""
        from third_chair.vault.session import SessionManager

        manager = SessionManager()
        salt = b"0" * 32

        manager.unlock_vault(tmp_path, "password", salt)
        session = manager.get_session(tmp_path)

        assert session is not None

    def test_get_session_nonexistent(self, tmp_path):
        """Test getting a nonexistent session returns None."""
        from third_chair.vault.session import SessionManager

        manager = SessionManager()
        session = manager.get_session(tmp_path)

        assert session is None

    def test_lock_vault(self, tmp_path):
        """Test locking a vault clears the session."""
        from third_chair.vault.session import SessionManager

        manager = SessionManager()
        salt = b"0" * 32

        manager.unlock_vault(tmp_path, "password", salt)
        assert manager.is_unlocked(tmp_path)

        manager.lock_vault(tmp_path)
        assert not manager.is_unlocked(tmp_path)

    def test_lock_all(self, tmp_path):
        """Test locking all vaults."""
        from third_chair.vault.session import SessionManager

        manager = SessionManager()
        salt = b"0" * 32

        # Unlock multiple vaults
        path1 = tmp_path / "case1"
        path1.mkdir()
        path2 = tmp_path / "case2"
        path2.mkdir()

        manager.unlock_vault(path1, "password", salt)
        manager.unlock_vault(path2, "password", salt)

        count = manager.lock_all()

        assert count == 2
        assert not manager.is_unlocked(path1)
        assert not manager.is_unlocked(path2)


class TestVaultManager:
    """Tests for vault manager operations."""

    @pytest.fixture
    def vault_case_dir(self, tmp_path):
        """Create a case directory for vault testing."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        (case_dir / "extracted").mkdir()

        # Create case.json
        case_data = {
            "case_id": "TEST-VAULT",
            "court_case": "50-2025-CF-000001",
            "created_at": datetime.now().isoformat(),
            "evidence_items": [],
            "witnesses": {"witnesses": []},
            "timeline": [],
            "propositions": [],
            "material_issues": [],
            "metadata": {},
        }
        (case_dir / "case.json").write_text(json.dumps(case_data))

        return case_dir

    def test_vault_not_encrypted_initially(self, vault_case_dir):
        """Test case starts unencrypted."""
        from third_chair.vault import is_vault_encrypted

        assert not is_vault_encrypted(vault_case_dir)

    def test_initialize_vault(self, vault_case_dir):
        """Test initializing a vault."""
        from third_chair.vault import VaultManager, is_vault_encrypted

        vm = VaultManager(vault_case_dir)
        vm.initialize("secure_password_123")

        assert is_vault_encrypted(vault_case_dir)
        assert (vault_case_dir / "vault.meta").exists()

    def test_initialize_vault_weak_password(self, vault_case_dir):
        """Test initialization rejects weak passwords."""
        from third_chair.vault import VaultManager

        vm = VaultManager(vault_case_dir)

        with pytest.raises(ValueError, match="at least 8 characters"):
            vm.initialize("short")

    def test_verify_password(self, vault_case_dir):
        """Test password verification."""
        from third_chair.vault import VaultManager

        vm = VaultManager(vault_case_dir)
        vm.initialize("secure_password_123")

        assert vm.verify_password("secure_password_123")
        assert not vm.verify_password("wrong_password")

    def test_unlock_vault(self, vault_case_dir):
        """Test unlocking a vault."""
        from third_chair.vault import VaultManager, is_vault_unlocked
        from third_chair.vault.session import SessionManager

        # Reset singleton for clean test
        SessionManager.reset_instance()

        vm = VaultManager(vault_case_dir)
        vm.initialize("secure_password_123")

        # Lock after initialization
        from third_chair.vault import lock_vault
        lock_vault(vault_case_dir)
        assert not is_vault_unlocked(vault_case_dir)

        # Unlock
        session = vm.unlock("secure_password_123")
        assert session is not None
        assert is_vault_unlocked(vault_case_dir)

    def test_unlock_vault_wrong_password(self, vault_case_dir):
        """Test unlocking with wrong password fails."""
        from third_chair.vault import VaultManager, InvalidPasswordError

        vm = VaultManager(vault_case_dir)
        vm.initialize("secure_password_123")

        # Lock and try wrong password
        from third_chair.vault import lock_vault
        lock_vault(vault_case_dir)

        with pytest.raises(InvalidPasswordError):
            vm.unlock("wrong_password")

    def test_encrypt_decrypt_data(self, vault_case_dir):
        """Test encrypting and decrypting data in memory."""
        from third_chair.vault import VaultManager

        vm = VaultManager(vault_case_dir)
        vm.initialize("secure_password_123")

        original_data = b"Sensitive legal data"

        encrypted = vm.encrypt_data(original_data)
        decrypted = vm.decrypt_data(encrypted)

        assert decrypted == original_data
        assert encrypted != original_data

    def test_encrypt_decrypt_json(self, vault_case_dir):
        """Test encrypting and decrypting JSON data."""
        from third_chair.vault import VaultManager

        vm = VaultManager(vault_case_dir)
        vm.initialize("secure_password_123")

        data = {"name": "Test", "value": 123, "nested": {"key": "value"}}
        encrypted_path = vault_case_dir / "test.json.enc"

        vm.encrypt_json(data, encrypted_path)
        assert encrypted_path.exists()

        decrypted = vm.decrypt_json(encrypted_path)
        assert decrypted == data


class TestVaultMetadata:
    """Tests for vault metadata handling."""

    def test_metadata_serialization(self):
        """Test metadata serialization roundtrip."""
        from third_chair.vault.vault_manager import VaultMetadata

        metadata = VaultMetadata(
            version=1,
            algorithm="AES-256-GCM",
            key_derivation="PBKDF2-HMAC-SHA256",
            iterations=480_000,
            salt=b"test_salt_bytes_here",
            verification_hash=b"test_verification_hash",
            created_at="2025-01-15T10:00:00",
        )

        json_str = metadata.to_json()
        restored = VaultMetadata.from_json(json_str)

        assert restored.version == metadata.version
        assert restored.algorithm == metadata.algorithm
        assert restored.iterations == metadata.iterations
        assert restored.salt == metadata.salt
        assert restored.verification_hash == metadata.verification_hash


class TestMigration:
    """Tests for vault migration tools."""

    @pytest.fixture
    def unencrypted_case(self, tmp_path):
        """Create an unencrypted case for migration testing."""
        case_dir = tmp_path / "test_case"
        case_dir.mkdir()
        extracted = case_dir / "extracted"
        extracted.mkdir()

        # Create case.json
        case_data = {
            "case_id": "MIGRATE-001",
            "court_case": "50-2025-CF-000001",
            "created_at": datetime.now().isoformat(),
            "evidence_items": [],
            "witnesses": {"witnesses": []},
            "timeline": [],
            "propositions": [],
            "material_issues": [],
            "metadata": {},
        }
        (case_dir / "case.json").write_text(json.dumps(case_data))

        # Create some evidence files
        (extracted / "video.mp4").write_bytes(b"fake video content " * 100)
        (extracted / "document.pdf").write_bytes(b"fake pdf content " * 50)

        return case_dir

    def test_encrypt_existing_case(self, unencrypted_case):
        """Test encrypting an existing case."""
        from third_chair.vault import encrypt_existing_case, is_vault_encrypted
        from third_chair.vault.session import SessionManager

        # Reset singleton
        SessionManager.reset_instance()

        stats = encrypt_existing_case(
            unencrypted_case,
            "secure_password_123",
            show_progress=False,
        )

        assert is_vault_encrypted(unencrypted_case)
        assert stats["files_encrypted"] > 0
        assert stats["errors"] == []

        # Original files should be removed
        assert not (unencrypted_case / "case.json").exists()
        assert (unencrypted_case / "case.json.enc").exists()

    def test_encrypt_already_encrypted(self, unencrypted_case):
        """Test encrypting already encrypted case fails."""
        from third_chair.vault import encrypt_existing_case, VaultAlreadyExistsError
        from third_chair.vault.session import SessionManager

        SessionManager.reset_instance()

        # Encrypt once
        encrypt_existing_case(unencrypted_case, "password123", show_progress=False)

        # Try again
        with pytest.raises(VaultAlreadyExistsError):
            encrypt_existing_case(unencrypted_case, "password123", show_progress=False)

    def test_verify_vault_integrity(self, unencrypted_case):
        """Test vault integrity verification."""
        from third_chair.vault import encrypt_existing_case, verify_vault_integrity
        from third_chair.vault.session import SessionManager

        SessionManager.reset_instance()

        password = "secure_password_123"
        encrypt_existing_case(unencrypted_case, password, show_progress=False)

        stats = verify_vault_integrity(unencrypted_case, password, show_progress=False)

        assert stats["files_verified"] > 0
        assert stats["files_failed"] == 0


class TestEncryptedPath:
    """Tests for EncryptedPath wrapper."""

    @pytest.fixture
    def encrypted_case(self, tmp_path):
        """Create an encrypted case for testing."""
        from third_chair.vault import encrypt_existing_case
        from third_chair.vault.session import SessionManager

        SessionManager.reset_instance()

        case_dir = tmp_path / "enc_case"
        case_dir.mkdir()
        extracted = case_dir / "extracted"
        extracted.mkdir()

        # Create case.json
        case_data = {
            "case_id": "ENC-001",
            "created_at": datetime.now().isoformat(),
            "evidence_items": [],
            "witnesses": {"witnesses": []},
            "timeline": [],
            "propositions": [],
            "material_issues": [],
            "metadata": {},
        }
        (case_dir / "case.json").write_text(json.dumps(case_data))

        # Create test file
        test_file = extracted / "test.txt"
        test_file.write_text("This is test content for encryption.")

        # Encrypt
        encrypt_existing_case(case_dir, "test_password_123", show_progress=False)

        return case_dir

    def test_encrypted_path_read_bytes(self, encrypted_case):
        """Test reading bytes through EncryptedPath."""
        from third_chair.vault import VaultManager, get_vault_session
        from third_chair.vault.file_wrapper import EncryptedPath

        vm = VaultManager(encrypted_case)
        session = get_vault_session(encrypted_case)

        encrypted_file = encrypted_case / "extracted" / "test.txt.enc"
        enc_path = EncryptedPath(encrypted_file, session, vm)

        content = enc_path.read_bytes()
        assert b"test content" in content

    def test_encrypted_path_read_text(self, encrypted_case):
        """Test reading text through EncryptedPath."""
        from third_chair.vault import VaultManager, get_vault_session
        from third_chair.vault.file_wrapper import EncryptedPath

        vm = VaultManager(encrypted_case)
        session = get_vault_session(encrypted_case)

        encrypted_file = encrypted_case / "extracted" / "test.txt.enc"
        enc_path = EncryptedPath(encrypted_file, session, vm)

        content = enc_path.read_text()
        assert "test content" in content

    def test_encrypted_path_name(self, encrypted_case):
        """Test EncryptedPath returns original filename."""
        from third_chair.vault import VaultManager, get_vault_session
        from third_chair.vault.file_wrapper import EncryptedPath

        vm = VaultManager(encrypted_case)
        session = get_vault_session(encrypted_case)

        encrypted_file = encrypted_case / "extracted" / "test.txt.enc"
        enc_path = EncryptedPath(encrypted_file, session, vm)

        assert enc_path.name == "test.txt"
        assert enc_path.suffix == ".txt"


class TestVaultConfig:
    """Tests for vault configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        from third_chair.vault import VaultConfig

        config = VaultConfig()

        assert config.pbkdf2_iterations == 480_000
        assert config.session_timeout_minutes == 30
        assert config.encrypted_extension == ".enc"
        assert config.metadata_file == "vault.meta"

    def test_get_set_config(self):
        """Test getting and setting global config."""
        from third_chair.vault import get_vault_config, set_vault_config, VaultConfig

        original = get_vault_config()

        # Set custom config
        custom = VaultConfig(session_timeout_minutes=60)
        set_vault_config(custom)

        assert get_vault_config().session_timeout_minutes == 60

        # Restore original
        set_vault_config(original)
