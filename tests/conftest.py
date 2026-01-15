"""Shared pytest fixtures for Third Chair tests."""

import json
from datetime import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a clean temporary directory for each test."""
    return tmp_path


@pytest.fixture
def sample_case_dir(tmp_path: Path) -> Path:
    """Create a minimal case directory structure."""
    case_dir = tmp_path / "test_case"
    case_dir.mkdir()
    (case_dir / "extracted").mkdir()
    (case_dir / "reports").mkdir()
    return case_dir


@pytest.fixture
def sample_case(sample_case_dir: Path):
    """Create a minimal valid Case object for testing."""
    from third_chair.models import Case

    case = Case(
        case_id="TEST-001",
        court_case="50-2025-CF-000001",
        output_dir=sample_case_dir,
    )
    return case


@pytest.fixture
def sample_case_with_evidence(sample_case_dir: Path):
    """Create a Case with sample evidence items."""
    from third_chair.models import Case, EvidenceItem, FileType, ContentType

    # Create a dummy video file
    video_file = sample_case_dir / "extracted" / "bodycam_001.mp4"
    video_file.write_bytes(b"fake video content")

    # Create a dummy document
    doc_file = sample_case_dir / "extracted" / "report.pdf"
    doc_file.write_bytes(b"fake pdf content")

    case = Case(
        case_id="TEST-002",
        court_case="50-2025-CF-000002",
        output_dir=sample_case_dir,
    )

    case.add_evidence(EvidenceItem(
        id="EVD-001",
        filename="bodycam_001.mp4",
        file_path=video_file,
        file_type=FileType.VIDEO,
        content_type=ContentType.BWC_FOOTAGE,
        size_bytes=video_file.stat().st_size,
        duration_seconds=120.5,
    ))

    case.add_evidence(EvidenceItem(
        id="EVD-002",
        filename="report.pdf",
        file_path=doc_file,
        file_type=FileType.DOCUMENT,
        content_type=ContentType.POLICE_REPORT,
        size_bytes=doc_file.stat().st_size,
    ))

    return case


@pytest.fixture
def sample_evidence_item(tmp_path: Path):
    """Create a sample EvidenceItem with a dummy file."""
    from third_chair.models import EvidenceItem, FileType, ContentType

    # Create a dummy file
    test_file = tmp_path / "test_video.mp4"
    test_file.write_bytes(b"test content")

    return EvidenceItem(
        id="EVD-001",
        filename="test_video.mp4",
        file_path=test_file,
        file_type=FileType.VIDEO,
        content_type=ContentType.BWC_FOOTAGE,
        size_bytes=test_file.stat().st_size,
        duration_seconds=60.0,
    )


@pytest.fixture
def sample_transcript():
    """Create a Transcript with a few segments for testing."""
    from third_chair.models import Transcript, TranscriptSegment

    segments = [
        TranscriptSegment(
            start=0.0,
            end=5.0,
            text="This is the first segment.",
            speaker="SPEAKER_1",
            confidence=0.95,
        ),
        TranscriptSegment(
            start=5.0,
            end=10.0,
            text="This is the second segment.",
            speaker="SPEAKER_2",
            confidence=0.88,
        ),
        TranscriptSegment(
            start=10.0,
            end=15.0,
            text="And this is the third segment.",
            speaker="SPEAKER_1",
            confidence=0.92,
        ),
    ]

    return Transcript(
        segments=segments,
        speakers={"SPEAKER_1": "Officer Smith", "SPEAKER_2": "Witness Jones"},
        language="en",
    )


@pytest.fixture
def work_storage(sample_case_dir: Path):
    """Create an initialized WorkStorage for testing."""
    from third_chair.work import WorkStorage, init_work_storage

    storage = init_work_storage(sample_case_dir, case_id="TEST-001")
    return storage


@pytest.fixture
def work_storage_with_items(work_storage):
    """WorkStorage with pre-populated work items for testing."""
    from third_chair.work import WorkItemType

    # Create items of different types
    work_storage.create_item(
        item_type=WorkItemType.INVESTIGATION,
        title="Interview witness",
        description="Interview Maria Garcia about the incident",
        priority="high",
    )

    work_storage.create_item(
        item_type=WorkItemType.LEGAL_QUESTION,
        title="Self-defense burden",
        description="Research burden of proof for self-defense claim",
        priority="medium",
    )

    work_storage.create_item(
        item_type=WorkItemType.ACTION,
        title="File motion to suppress",
        description="Prepare and file motion to suppress evidence",
        priority="critical",
    )

    return work_storage


@pytest.fixture
def mock_ollama():
    """Mock Ollama client to avoid network calls."""
    mock_response = MagicMock()
    mock_response.success = True
    mock_response.text = json.dumps({
        "tool": "search_evidence",
        "params": {"query": "test"},
        "confidence": 0.85,
        "interpretation": "Search for evidence matching 'test'",
        "alternatives": [],
    })
    mock_response.error = None

    mock_client = MagicMock()
    mock_client.is_available.return_value = True
    mock_client.generate.return_value = mock_response

    with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_ollama_unavailable():
    """Mock Ollama client that is unavailable."""
    mock_client = MagicMock()
    mock_client.is_available.return_value = False

    with patch("third_chair.chat.intent_extractor.get_ollama_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def sample_tool_schemas() -> list[dict]:
    """Sample tool schemas for intent extraction tests."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_evidence",
                "description": "Search evidence items by keyword",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_witnesses",
                "description": "List all witnesses in the case",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "name": "show_timeline",
            "description": "Show case timeline",
            "parameters": {"type": "object", "properties": {}},
        },
    ]


@pytest.fixture
def sample_case_json() -> dict:
    """Sample case.json data for loading tests."""
    return {
        "case_id": "TEST-001",
        "court_case": "50-2025-CF-000001",
        "created_at": "2025-01-15T10:00:00",
        "output_dir": "/tmp/test_case",
        "evidence_items": [
            {
                "id": "EVD-001",
                "filename": "bodycam_001.mp4",
                "file_path": "/tmp/test_case/extracted/bodycam_001.mp4",
                "file_type": "video",
                "content_type": "bwc_footage",
                "size_bytes": 1024000,
                "processing_status": "pending",
                "created_at": "2025-01-15T10:00:00",
            }
        ],
        "witnesses": {"witnesses": []},
        "timeline": [],
        "propositions": [],
        "material_issues": [],
        "metadata": {},
    }
