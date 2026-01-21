# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Third Chair is a legal discovery processing tool for Axon body-worn camera evidence packages. It transcribes audio/video, detects and translates Spanish content, manages witnesses, and generates attorney-ready reports with Bates numbering.

**Target Users**: Criminal defense attorneys processing body-worn camera evidence.

**Key Capabilities**:
- Axon ZIP ingestion and file classification
- CPU-optimized transcription (faster-whisper) with speaker diarization
- Spanish/English translation via local Ollama
- Evidence workbench for inconsistency detection
- Skanda Framework for legal proposition evaluation
- Case encryption (AES-256 vault)
- Attorney reports with Bates numbering

## Build & Development Commands

```bash
# Install in development mode
pip install -e .

# Run CLI directly (without installation)
python -m third_chair.cli.main <command>

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/unit/test_file.py::test_function -v

# Lint (ruff)
ruff check third_chair/

# Type check
mypy third_chair/

# System dependencies (Ubuntu/WSL)
sudo apt-get install tesseract-ocr ffmpeg
```

## Ollama Management

```bash
# Required models
ollama pull aya-expanse:8b     # Translation
ollama pull mistral:7b         # Summarization, extraction
ollama pull nomic-embed-text   # Embeddings (workbench)

# Unload idle models (prevents CPU thrashing)
curl http://localhost:11434/api/generate -d '{"model": "MODEL_NAME", "keep_alive": 0}'

# Restart if slow (stuck model runners)
sudo snap restart ollama
```

## Architecture

### Module Organization

| Module | Purpose |
|--------|---------|
| `cli/` | Typer CLI (`main.py` has all commands) |
| `tui/` | Textual TUI (app.py, screens.py, widgets.py) |
| `models/` | Dataclasses: Case, EvidenceItem, Transcript, Proposition |
| `ingest/` | ZIP extraction, file classification, ToC parsing |
| `transcription/` | faster-whisper + pyannote diarization |
| `translation/` | fast-langdetect language detection + Ollama translation |
| `documents/` | PDF/DOCX/image processing, OCR, frame extraction |
| `summarization/` | Ollama-powered summaries, timeline builder |
| `analysis/` | Skanda Framework proposition evaluation |
| `witnesses/` | Witness import, speaker role detection |
| `reports/` | DOCX/PDF generation with Bates numbering |
| `chat/` | Research assistant tools |
| `staging/` | ZIP import staging with preview and batch processing |
| `vault/` | AES-256 case encryption, session management |
| `work/` | Work item management (investigations, actions, objectives) |
| `workbench/` | Evidence extraction, embedding, inconsistency detection |
| `config/` | Settings and configuration |
| `utils/` | Logging, hashing, place names |

### Pipeline Entry Points

Each module exposes a main function in `__init__.py`:

```python
from third_chair.ingest import ingest_axon_package
from third_chair.transcription import transcribe_case
from third_chair.translation import translate_case
from third_chair.summarization import summarize_case_evidence
from third_chair.workbench import init_workbench, get_workbench_db
from third_chair.workbench.extraction import extract_from_case
from third_chair.workbench.embedding import embed_extractions
from third_chair.workbench.detection import detect_connections
```

CLI commands use lazy imports (import at function level) to speed startup.

## Core Data Models (third_chair/models/)

All models use `@dataclass` with `to_dict()` / `from_dict()` for JSON serialization.

**Case** (`case.py`): Central container with `evidence_items`, `witnesses`, `timeline`, `propositions`. Serializes to `case.json` via `case.save()`.

**EvidenceItem** (`evidence.py`): Individual file with `file_type` (VIDEO/AUDIO/DOCUMENT/IMAGE), `content_type` (BWC_FOOTAGE/CAD_LOG/etc), `transcript`, `processing_status`.

**Transcript** (`transcript.py`): Contains `segments` (TranscriptSegment list), `speakers` mapping (SPEAKER_1 → name), `key_statements`.

**TranscriptSegment**: Single utterance with `start_time`, `end_time`, `speaker`, `text`, `language`, `translation`, `review_flags`, `speaker_role`.

### Model Patterns

```python
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

class MyType(str, Enum):
    """Always use str, Enum for JSON-serializable enums."""
    VALUE_A = "value_a"
    VALUE_B = "value_b"

@dataclass
class MyModel:
    """Standard dataclass pattern."""
    id: str
    name: str
    optional_field: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "optional_field": self.optional_field,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MyModel":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            optional_field=data.get("optional_field"),
            metadata=data.get("metadata", {}),
        )
```

## Key CLI Commands

```bash
# Full pipeline
third-chair process case.zip --output ./my_case

# Individual steps
third-chair ingest case.zip --output ./my_case --court-case "50-2025-CF-001234"
third-chair transcribe ./my_case --whisper-model medium --no-diarization
third-chair translate ./my_case
third-chair summarize ./my_case
third-chair report ./my_case --format all --bates-prefix DEF

# Interactive
third-chair tui                    # TUI with case selection
third-chair chat ./my_case         # Research assistant

# Evidence Workbench
third-chair workbench init ./my_case
third-chair workbench extract ./my_case
third-chair workbench embed ./my_case
third-chair workbench detect ./my_case
third-chair workbench connections ./my_case
third-chair workbench status ./my_case

# Work Items
third-chair work list ./my_case
third-chair work add ./my_case --title "Review BWC footage" --type action
third-chair work update ./my_case INV-0001 --status completed

# Vault
third-chair vault-init ./case
third-chair vault-unlock ./case
third-chair vault-lock ./case
```

## Hardware Constraints

CPU-only inference environment (Intel UHD 630 iGPU, no CUDA):
- Ollama: Run ONE model at a time to avoid CPU thrashing (1800%+ CPU usage)
- Whisper: Uses int8 compute type for CPU optimization
- Typical Ollama response: ~2s when healthy, 30s+ when multiple models compete

## Common Tasks

### Adding a new file type
1. Add extension to `third_chair/models/evidence.py:FILE_TYPE_MAP`
2. Add content type pattern to `third_chair/ingest/file_classifier.py:CONTENT_TYPE_PATTERNS`

### Adding a new CLI command
1. Add function with `@app.command()` in `third_chair/cli/main.py`
2. Import any needed modules at function level (for lazy loading)
3. Use `console.print()` from Rich for output

Example:
```python
@app.command()
def my_command(
    case_dir: Path = typer.Argument(..., help="Path to case directory"),
    option: str = typer.Option("default", "--option", "-o", help="Description"),
):
    """Command docstring shown in help."""
    # Lazy import at function level
    from ..my_module import my_function

    if not case_dir.exists():
        console.print(f"[red]Error: Case directory not found: {case_dir}[/red]")
        raise typer.Exit(1)

    # ... implementation
    console.print("[green]Success![/green]")
```

### Adding a CLI subcommand group
```python
my_app = typer.Typer(
    name="mygroup",
    help="Description of the command group.",
    no_args_is_help=True,
)
app.add_typer(my_app, name="mygroup")

@my_app.command("subcommand")
def my_subcommand(...):
    """Subcommand docstring."""
    ...
```

### Modifying translation prompts
Edit `_build_translation_prompt()` in `third_chair/translation/ollama_translator.py`

### Modifying summarization prompts
Edit system prompts in `third_chair/summarization/ollama_client.py`

### Adding keyword detection
- Threats: Add to `THREAT_KEYWORDS` in `transcript_summarizer.py`
- Violence: Add to `VIOLENCE_KEYWORDS` in `transcript_summarizer.py`
- Officer indicators: Add to `OFFICER_INDICATORS` in `speaker_roles.py`

## Data Flow

1. **Ingest**: ZIP → Extract → Classify → Case with EvidenceItems
2. **Transcribe**: Media → FFmpeg normalize → Whisper → Diarize → Transcript
3. **Translate**: Transcript → Language detect → Ollama translate → Updated segments
4. **Documents**: PDF/DOCX/Image → Extract/OCR → Summary text
5. **Summarize**: Case → Transcript summaries → Timeline → Case summary
6. **Workbench**: Transcripts → Extract facts → Embed → Detect inconsistencies
7. **Report**: Case → Evidence inventory → Witness list → DOCX/PDF report

## Configuration

Environment variables (with defaults):
```bash
WHISPER_MODEL=medium
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TRANSLATION_MODEL=aya-expanse:8b
OLLAMA_SUMMARY_MODEL=mistral:7b
HF_TOKEN=  # Required for diarization
```

## Error Handling

- Processing errors: `evidence.error_message`
- Low confidence segments: `ReviewFlag.LOW_CONFIDENCE` flag
- Items needing review: `case.metadata["items_needing_review"]`

## Evidence Workbench

The workbench module extracts granular facts from transcripts and detects inconsistencies between evidence items.

### Components

| Component | Purpose |
|-----------|---------|
| `workbench/models.py` | `Extraction`, `SuggestedConnection` dataclasses |
| `workbench/database.py` | SQLite operations (`workbench.db`) |
| `workbench/extraction/` | LLM-based fact extraction from segments |
| `workbench/embedding/` | Vector embeddings via Ollama |
| `workbench/detection/` | Inconsistency and timeline conflict detection |

### Database Schema

```sql
-- Extractions: granular facts
CREATE TABLE extractions (
    id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    extraction_type TEXT NOT NULL,  -- statement, event, entity_mention, action
    content TEXT NOT NULL,
    speaker TEXT,
    start_time REAL,
    confidence REAL
);

-- Embeddings: vector storage
CREATE TABLE embeddings (
    extraction_id TEXT REFERENCES extractions(id),
    vector BLOB NOT NULL,
    model TEXT
);

-- Suggested connections
CREATE TABLE suggested_connections (
    id TEXT PRIMARY KEY,
    extraction_a_id TEXT REFERENCES extractions(id),
    extraction_b_id TEXT REFERENCES extractions(id),
    connection_type TEXT,  -- inconsistent_statement, temporal_conflict, corroborates
    confidence REAL,
    reasoning TEXT,
    severity TEXT,  -- minor, moderate, major, critical
    status TEXT DEFAULT 'pending'
);
```

### Usage

```python
from third_chair.workbench import init_workbench, get_workbench_db
from third_chair.workbench.extraction import extract_from_case
from third_chair.workbench.embedding import embed_extractions
from third_chair.workbench.detection import detect_connections

# Initialize
db = init_workbench(case_dir)

# Extract facts from transcripts
extract_from_case(case_dir, model="mistral:7b")

# Generate embeddings
embed_extractions(case_dir, model="nomic-embed-text")

# Detect inconsistencies
results = detect_connections(case_dir, types=["inconsistency", "timeline"])
```

## Work Items

The work module manages attorney tasks and investigations.

### Work Item Types
- `investigation` - Research tasks
- `legal_question` - Legal research questions
- `objective` - Case objectives
- `action` - Specific tasks
- `fact` - Facts to establish

### Storage
Work items are stored as YAML files in `case_dir/work/`:
```
work/
├── _index.yaml      # Index with metadata
├── INV-0001.yaml    # Individual items
├── ACT-0001.yaml
└── ...
```

### Usage

```python
from third_chair.work import WorkStorage, WorkItemType

storage = WorkStorage(case_dir)
item = storage.create_item(
    item_type=WorkItemType.ACTION,
    title="Review BWC footage",
    description="Look for exculpatory statements",
    priority="high",
)
```

## Vault Encryption

Case directories can be encrypted with AES-256 for client confidentiality.

### Key Components

- `vault/crypto.py`: AES-256-GCM and Fernet encryption
- `vault/session.py`: Session management with timeout
- `vault/vault_manager.py`: Vault operations (init, lock, unlock)
- `vault/file_wrapper.py`: Transparent file access (EncryptedPath)
- `vault/migration.py`: Encrypt existing, export, rotate password

### Usage

```python
from third_chair.vault import VaultManager, is_vault_encrypted

# Check if encrypted
if is_vault_encrypted(case_dir):
    vm = VaultManager(case_dir)
    vm.unlock(password)

# Encrypt existing case
from third_chair.vault import encrypt_existing_case
encrypt_existing_case(case_dir, password)
```

## Skanda Framework (Legal Proposition Evaluation)

The Skanda Framework treats "fact" as an earned output label, not a stored boolean. See `models/proposition.py` for full model definitions.

### Core Rules

1. **Never create a "fact" field.** Create a `Proposition` with `skanda` and `evaluation` instead.
2. **Every `Proposit` must have at least one `EvidenceRef`.** No bare assertions.
3. **Evaluator must be deterministic** with explanations citing driver proposits.
4. **Validate LLM JSON** against schema; reject if missing evidence references.

### Key Concepts

- **Proposition**: Assertion with `skanda` (basket of proposits) and computed `evaluation`
- **Proposit**: Atomic claim with `polarity` (supports/undermines) and `evidence_refs`
- **EvaluationSnapshot**: `holds_under_scrutiny` (tri-state: yes/no/uncertain), `weight`, `probative_value`

### Usage

```python
from third_chair.analysis import extract_propositions_from_case, evaluate_all_propositions

propositions = extract_propositions_from_case(case)
case.propositions = propositions
evaluate_all_propositions(case)
```

## Staging Area

Drop-folder workflow for batch ZIP imports.

### Key Components

- `staging/preview.py`: Quick ZIP preview without extraction
- `staging/manager.py`: Staging workflow (incoming → processing → cases)
- `staging/watcher.py`: Background folder watcher

### TUI Integration

Press `s` in TUI to open staging screen.

## Testing Patterns

```python
import pytest
from pathlib import Path
from third_chair.models import Case, EvidenceItem

def test_my_feature(tmp_path: Path):
    """Use tmp_path fixture for temporary directories."""
    case = Case(case_id="test-001", output_dir=tmp_path)
    # ... test implementation

@pytest.fixture
def sample_case(tmp_path: Path) -> Case:
    """Fixture for common test setup."""
    case = Case(case_id="test-001", output_dir=tmp_path)
    case.save()
    return case
```

## Code Style

- Use type hints everywhere
- Prefer `Path` over `str` for file paths
- Use `@dataclass` for data containers
- Use `Enum(str, Enum)` for string enums
- Lazy imports in CLI functions
- Rich console for CLI output
- httpx for HTTP clients (not requests)

## Dependencies

Key dependencies from `pyproject.toml`:
- `typer` - CLI framework
- `rich` - Console formatting
- `textual` - TUI framework
- `faster-whisper` - Transcription
- `httpx` - Ollama API client
- `pdfplumber` - PDF parsing
- `python-docx` - DOCX generation
- `numpy` - Vector operations (workbench)
