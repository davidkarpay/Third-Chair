"""SQLite database operations for the Evidence Workbench."""

import json
import sqlite3
from pathlib import Path
from typing import Optional

from .config import get_workbench_config
from .models import (
    ConnectionStatus,
    ConnectionType,
    Extraction,
    ExtractionType,
    Severity,
    SuggestedConnection,
)


SCHEMA_SQL = """
-- Extractions: granular facts from LLM
CREATE TABLE IF NOT EXISTS extractions (
    id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    segment_index INTEGER,
    extraction_type TEXT NOT NULL,
    content TEXT NOT NULL,
    speaker TEXT,
    speaker_role TEXT,
    start_time REAL,
    end_time REAL,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Embeddings: vector storage
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    extraction_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    vector BLOB NOT NULL,
    model TEXT DEFAULT 'nomic-embed-text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Suggested connections: detected relationships
CREATE TABLE IF NOT EXISTS suggested_connections (
    id TEXT PRIMARY KEY,
    extraction_a_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    extraction_b_id TEXT NOT NULL REFERENCES extractions(id) ON DELETE CASCADE,
    connection_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT NOT NULL,
    evidence_snippets TEXT,
    severity TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_extractions_evidence ON extractions(evidence_id);
CREATE INDEX IF NOT EXISTS idx_extractions_type ON extractions(extraction_type);
CREATE INDEX IF NOT EXISTS idx_embeddings_extraction ON embeddings(extraction_id);
CREATE INDEX IF NOT EXISTS idx_connections_status ON suggested_connections(status);
CREATE INDEX IF NOT EXISTS idx_connections_type ON suggested_connections(connection_type);
"""


class WorkbenchDB:
    """Database manager for the workbench SQLite database."""

    def __init__(self, case_dir: Path):
        """Initialize the database connection.

        Args:
            case_dir: Path to the case directory
        """
        config = get_workbench_config()
        self.db_path = case_dir / config.db_filename
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get the database connection, creating if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def create_schema(self) -> None:
        """Create the database schema if it doesn't exist."""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def is_initialized(self) -> bool:
        """Check if the database has been initialized."""
        if not self.db_path.exists():
            return False
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extractions'"
        )
        return cursor.fetchone() is not None

    # ===================
    # Extraction CRUD
    # ===================

    def add_extraction(self, extraction: Extraction) -> None:
        """Add an extraction to the database."""
        self.conn.execute(
            """
            INSERT INTO extractions (
                id, evidence_id, segment_index, extraction_type, content,
                speaker, speaker_role, start_time, end_time, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extraction.id,
                extraction.evidence_id,
                extraction.segment_index,
                extraction.extraction_type.value,
                extraction.content,
                extraction.speaker,
                extraction.speaker_role,
                extraction.start_time,
                extraction.end_time,
                extraction.confidence,
                extraction.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def add_extractions_batch(self, extractions: list[Extraction]) -> None:
        """Add multiple extractions in a single transaction."""
        self.conn.executemany(
            """
            INSERT INTO extractions (
                id, evidence_id, segment_index, extraction_type, content,
                speaker, speaker_role, start_time, end_time, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    e.id,
                    e.evidence_id,
                    e.segment_index,
                    e.extraction_type.value,
                    e.content,
                    e.speaker,
                    e.speaker_role,
                    e.start_time,
                    e.end_time,
                    e.confidence,
                    e.created_at.isoformat(),
                )
                for e in extractions
            ],
        )
        self.conn.commit()

    def get_extraction(self, extraction_id: str) -> Optional[Extraction]:
        """Get a single extraction by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM extractions WHERE id = ?", (extraction_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_extraction(row)
        return None

    def get_extractions(
        self,
        evidence_id: Optional[str] = None,
        extraction_type: Optional[ExtractionType] = None,
        limit: Optional[int] = None,
    ) -> list[Extraction]:
        """Get extractions with optional filters."""
        query = "SELECT * FROM extractions WHERE 1=1"
        params: list = []

        if evidence_id:
            query += " AND evidence_id = ?"
            params.append(evidence_id)
        if extraction_type:
            query += " AND extraction_type = ?"
            params.append(extraction_type.value)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        return [self._row_to_extraction(row) for row in cursor.fetchall()]

    def get_extraction_count(self) -> int:
        """Get total number of extractions."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM extractions")
        return cursor.fetchone()[0]

    def delete_extractions_for_evidence(self, evidence_id: str) -> int:
        """Delete all extractions for an evidence item."""
        cursor = self.conn.execute(
            "DELETE FROM extractions WHERE evidence_id = ?", (evidence_id,)
        )
        self.conn.commit()
        return cursor.rowcount

    def _row_to_extraction(self, row: sqlite3.Row) -> Extraction:
        """Convert a database row to an Extraction."""
        from datetime import datetime

        return Extraction(
            id=row["id"],
            evidence_id=row["evidence_id"],
            segment_index=row["segment_index"],
            extraction_type=ExtractionType(row["extraction_type"]),
            content=row["content"],
            speaker=row["speaker"],
            speaker_role=row["speaker_role"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            confidence=row["confidence"],
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else datetime.now(),
        )

    # ===================
    # Embedding CRUD
    # ===================

    def add_embedding(
        self, extraction_id: str, vector: bytes, model: str = "nomic-embed-text"
    ) -> None:
        """Add an embedding for an extraction."""
        self.conn.execute(
            "INSERT INTO embeddings (extraction_id, vector, model) VALUES (?, ?, ?)",
            (extraction_id, vector, model),
        )
        self.conn.commit()

    def add_embeddings_batch(
        self, embeddings: list[tuple[str, bytes]], model: str = "nomic-embed-text"
    ) -> None:
        """Add multiple embeddings in a single transaction.

        Args:
            embeddings: List of (extraction_id, vector_bytes) tuples
            model: The embedding model name
        """
        self.conn.executemany(
            "INSERT INTO embeddings (extraction_id, vector, model) VALUES (?, ?, ?)",
            [(eid, vec, model) for eid, vec in embeddings],
        )
        self.conn.commit()

    def get_embedding(self, extraction_id: str) -> Optional[bytes]:
        """Get the embedding vector for an extraction."""
        cursor = self.conn.execute(
            "SELECT vector FROM embeddings WHERE extraction_id = ?", (extraction_id,)
        )
        row = cursor.fetchone()
        return row["vector"] if row else None

    def get_all_embeddings(self) -> list[tuple[str, bytes]]:
        """Get all embeddings as (extraction_id, vector) tuples."""
        cursor = self.conn.execute("SELECT extraction_id, vector FROM embeddings")
        return [(row["extraction_id"], row["vector"]) for row in cursor.fetchall()]

    def get_embedding_count(self) -> int:
        """Get total number of embeddings."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM embeddings")
        return cursor.fetchone()[0]

    def has_embedding(self, extraction_id: str) -> bool:
        """Check if an extraction has an embedding."""
        cursor = self.conn.execute(
            "SELECT 1 FROM embeddings WHERE extraction_id = ?", (extraction_id,)
        )
        return cursor.fetchone() is not None

    # ===================
    # Connection CRUD
    # ===================

    def add_connection(self, connection: SuggestedConnection) -> None:
        """Add a suggested connection to the database."""
        self.conn.execute(
            """
            INSERT INTO suggested_connections (
                id, extraction_a_id, extraction_b_id, connection_type,
                confidence, reasoning, evidence_snippets, severity, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connection.id,
                connection.extraction_a_id,
                connection.extraction_b_id,
                connection.connection_type.value,
                connection.confidence,
                connection.reasoning,
                json.dumps(connection.evidence_snippets),
                connection.severity.value if connection.severity else None,
                connection.status.value,
                connection.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def add_connections_batch(self, connections: list[SuggestedConnection]) -> None:
        """Add multiple connections in a single transaction."""
        self.conn.executemany(
            """
            INSERT INTO suggested_connections (
                id, extraction_a_id, extraction_b_id, connection_type,
                confidence, reasoning, evidence_snippets, severity, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    c.id,
                    c.extraction_a_id,
                    c.extraction_b_id,
                    c.connection_type.value,
                    c.confidence,
                    c.reasoning,
                    json.dumps(c.evidence_snippets),
                    c.severity.value if c.severity else None,
                    c.status.value,
                    c.created_at.isoformat(),
                )
                for c in connections
            ],
        )
        self.conn.commit()

    def get_connection(self, connection_id: str) -> Optional[SuggestedConnection]:
        """Get a single connection by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM suggested_connections WHERE id = ?", (connection_id,)
        )
        row = cursor.fetchone()
        if row:
            return self._row_to_connection(row)
        return None

    def get_connections(
        self,
        connection_type: Optional[ConnectionType] = None,
        status: Optional[ConnectionStatus] = None,
        limit: Optional[int] = None,
    ) -> list[SuggestedConnection]:
        """Get connections with optional filters."""
        query = "SELECT * FROM suggested_connections WHERE 1=1"
        params: list = []

        if connection_type:
            query += " AND connection_type = ?"
            params.append(connection_type.value)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY confidence DESC, created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        return [self._row_to_connection(row) for row in cursor.fetchall()]

    def get_connection_count(
        self,
        connection_type: Optional[ConnectionType] = None,
        status: Optional[ConnectionStatus] = None,
    ) -> int:
        """Get count of connections with optional filters."""
        query = "SELECT COUNT(*) FROM suggested_connections WHERE 1=1"
        params: list = []

        if connection_type:
            query += " AND connection_type = ?"
            params.append(connection_type.value)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        cursor = self.conn.execute(query, params)
        return cursor.fetchone()[0]

    def update_connection_status(
        self, connection_id: str, status: ConnectionStatus
    ) -> bool:
        """Update the status of a connection."""
        cursor = self.conn.execute(
            "UPDATE suggested_connections SET status = ? WHERE id = ?",
            (status.value, connection_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_connections_by_type(self, connection_type: ConnectionType) -> int:
        """Delete all connections of a specific type."""
        cursor = self.conn.execute(
            "DELETE FROM suggested_connections WHERE connection_type = ?",
            (connection_type.value,),
        )
        self.conn.commit()
        return cursor.rowcount

    def _row_to_connection(self, row: sqlite3.Row) -> SuggestedConnection:
        """Convert a database row to a SuggestedConnection."""
        from datetime import datetime

        return SuggestedConnection(
            id=row["id"],
            extraction_a_id=row["extraction_a_id"],
            extraction_b_id=row["extraction_b_id"],
            connection_type=ConnectionType(row["connection_type"]),
            confidence=row["confidence"],
            reasoning=row["reasoning"],
            evidence_snippets=json.loads(row["evidence_snippets"])
            if row["evidence_snippets"]
            else [],
            severity=Severity(row["severity"]) if row["severity"] else None,
            status=ConnectionStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else datetime.now(),
        )

    # ===================
    # Statistics
    # ===================

    def get_stats(self) -> dict:
        """Get workbench statistics."""
        return {
            "extractions": self.get_extraction_count(),
            "embeddings": self.get_embedding_count(),
            "connections_total": self.get_connection_count(),
            "connections_pending": self.get_connection_count(
                status=ConnectionStatus.PENDING
            ),
            "connections_confirmed": self.get_connection_count(
                status=ConnectionStatus.CONFIRMED
            ),
            "connections_by_type": {
                ct.value: self.get_connection_count(connection_type=ct)
                for ct in ConnectionType
            },
        }


def get_workbench_db(case_dir: Path) -> WorkbenchDB:
    """Get a WorkbenchDB instance for a case directory."""
    return WorkbenchDB(case_dir)


def init_workbench(case_dir: Path) -> WorkbenchDB:
    """Initialize the workbench database for a case.

    Creates the database file and schema if they don't exist.

    Args:
        case_dir: Path to the case directory

    Returns:
        Initialized WorkbenchDB instance
    """
    db = WorkbenchDB(case_dir)
    db.create_schema()
    return db
