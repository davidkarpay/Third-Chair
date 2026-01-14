# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Third Chair is a legal discovery processing tool for Axon body-worn camera evidence packages. It transcribes audio/video, detects and translates Spanish content, manages witnesses, and generates attorney-ready reports with Bates numbering.

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
ollama pull aya-expanse:8b   # Translation
ollama pull mistral:7b       # Summarization

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
| `translation/` | FastText language detection + Ollama translation |
| `documents/` | PDF/DOCX/image processing, OCR, frame extraction |
| `summarization/` | Ollama-powered summaries, timeline builder |
| `analysis/` | Skanda Framework proposition evaluation |
| `witnesses/` | Witness import, speaker role detection |
| `reports/` | DOCX/PDF generation with Bates numbering |
| `chat/` | Research assistant tools |

### Pipeline Entry Points

Each module exposes a main function in `__init__.py`:

```python
from third_chair.ingest import ingest_axon_package
from third_chair.transcription import transcribe_case
from third_chair.translation import translate_case
from third_chair.summarization import summarize_case_evidence
```

CLI commands use lazy imports (import at function level) to speed startup.

## Core Data Models (third_chair/models/)

**Case** (`case.py`): Central container with `evidence_items`, `witnesses`, `timeline`, `propositions`. Serializes to `case.json` via `case.save()`.

**EvidenceItem** (`evidence.py`): Individual file with `file_type` (VIDEO/AUDIO/DOCUMENT/IMAGE), `content_type` (BWC_FOOTAGE/CAD_LOG/etc), `transcript`, `processing_status`.

**Transcript** (`transcript.py`): Contains `segments` (TranscriptSegment list), `speakers` mapping (SPEAKER_1 → name), `key_statements`.

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
6. **Report**: Case → Evidence inventory → Witness list → DOCX/PDF report

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
