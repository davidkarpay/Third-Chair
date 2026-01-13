# Third Chair - AI Assistant Instructions

## Project Overview

Third Chair is a legal discovery processing tool for Axon body-worn camera evidence packages. It transcribes audio/video, detects and translates Spanish content, manages witnesses, and generates attorney-ready reports with Bates numbering.

## Architecture

```
third_chair/
├── config/          # Configuration settings
│   └── settings.py  # Dataclass-based config with env var overrides
├── ingest/          # ZIP extraction, file classification
│   ├── zip_extractor.py    # Axon ZIP extraction
│   ├── file_classifier.py  # Auto-categorize files
│   ├── metadata_parser.py  # Parse Axon filename patterns
│   └── toc_parser.py       # Parse Table_of_Contents.xlsx
├── transcription/   # Whisper transcription, diarization
│   ├── media_processor.py      # FFmpeg normalization (16kHz mono)
│   ├── whisper_transcribe.py   # faster-whisper wrapper
│   ├── diarize.py              # pyannote speaker diarization
│   └── segment_consolidator.py # Merge fragmented segments
├── translation/     # Ollama translation, language detection
│   ├── language_detector.py   # FastText + keyword detection
│   ├── ollama_translator.py   # Ollama API wrapper
│   └── phrase_extractor.py    # Spanish phrase extraction
├── witnesses/       # Witness management
│   ├── speaker_roles.py       # Officer/Victim/Witness detection
│   ├── witness_importer.py    # Multi-format import (PDF, DOCX, XLSX)
│   └── witness_matcher.py     # Match witnesses to speakers
├── documents/       # PDF/DOCX/image processing
│   ├── pdf_extractor.py    # pdfplumber + OCR fallback
│   ├── docx_parser.py      # Word + Axon transcript parsing
│   └── image_processor.py  # pytesseract OCR
├── summarization/   # AI summaries via Ollama
│   ├── ollama_client.py        # Ollama API wrapper
│   ├── transcript_summarizer.py # Per-transcript summaries
│   ├── timeline_builder.py     # Chronological timeline
│   └── case_summarizer.py      # Executive case summary
├── reports/         # Report generation
│   ├── evidence_inventory.py # Evidence catalog
│   ├── docx_generator.py     # Word document output
│   ├── pdf_generator.py      # PDF with Bates numbering
│   └── attorney_report.py    # Unified report generation
├── models/          # Data models
│   ├── case.py       # Case with evidence, witnesses, timeline
│   ├── evidence.py   # EvidenceItem with file type/content type
│   ├── transcript.py # Transcript with segments, speakers, flags
│   └── witness.py    # Witness with roles and speaker IDs
├── cli/             # Typer CLI interface
│   └── main.py      # All CLI commands
└── utils/           # Utilities
    ├── logging.py   # Rich-based logging
    ├── places.py    # Place name preservation
    └── hash.py      # SHA-256 file hashing
```

## Key Files

- `third_chair/cli/main.py` - CLI entry point with all commands
- `third_chair/models/case.py` - Main Case data model (JSON serializable)
- `third_chair/ingest/__init__.py` - Evidence ingestion pipeline
- `third_chair/transcription/__init__.py` - Transcription pipeline
- `third_chair/translation/__init__.py` - Translation pipeline
- `third_chair/summarization/__init__.py` - Summarization pipeline
- `third_chair/reports/__init__.py` - Report generation pipeline

## Data Models

### Case
```python
@dataclass
class Case:
    case_id: str
    court_case: Optional[str]
    agency: Optional[str]
    incident_date: Optional[date]
    evidence_items: list[EvidenceItem]
    witnesses: WitnessList
    timeline: list[TimelineEvent]
    summary: Optional[str]
    metadata: dict
```

### EvidenceItem
```python
@dataclass
class EvidenceItem:
    id: str
    filename: str
    file_type: FileType  # VIDEO, AUDIO, DOCUMENT, IMAGE
    content_type: ContentType  # BWC_FOOTAGE, CAD_LOG, etc.
    file_path: Path
    size_bytes: int
    duration_seconds: Optional[float]
    transcript: Optional[Transcript]
    summary: Optional[str]
    processing_status: ProcessingStatus
```

### Transcript
```python
@dataclass
class Transcript:
    evidence_id: str
    segments: list[TranscriptSegment]
    speakers: dict[str, str]  # SPEAKER_1 -> "Officer Smith"
    key_statements: list[TranscriptSegment]
```

## CLI Commands

| Command | Function | Key Options |
|---------|----------|-------------|
| `process` | Full pipeline | `--skip-transcription`, `--skip-translation`, `--skip-summarization` |
| `ingest` | Extract ZIP | `--output`, `--court-case` |
| `transcribe` | Whisper transcription | `--whisper-model`, `--no-diarization` |
| `translate` | Spanish translation | `--ollama-model` |
| `documents` | PDF/DOCX/OCR | `--no-ocr`, `--extract` |
| `summarize` | AI summaries | `--timeline`, `--output` |
| `witnesses` | Witness management | `--import`, `--rename`, `--suggest` |
| `report` | Generate reports | `--format`, `--bates-prefix`, `--prepared-by` |
| `info` | ZIP contents | - |
| `status` | Case status | - |

## Hardware Constraints

This project is designed for CPU-only inference:
- Intel UHD 630 iGPU (no CUDA available)
- Ollama runs one model at a time to avoid CPU thrashing
- Whisper uses int8 compute type for CPU optimization
- Typical response times: ~2s per Ollama inference when single model loaded

## Development

### Running the CLI
```bash
python -m third_chair.cli.main process input.zip
# or after installing:
third-chair process input.zip
```

### Testing
```bash
pytest tests/ -v
```

### Dependencies
- `faster-whisper` - Transcription (CPU optimized)
- `pyannote.audio` - Speaker diarization (requires HF_TOKEN)
- `httpx` - Ollama API client
- `typer` + `rich` - CLI
- `pdfplumber` + `pytesseract` - PDF/image OCR
- `python-docx` - Word documents
- `reportlab` - PDF generation

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

- Processing errors are stored in `evidence.error_message`
- Low confidence segments are flagged with `ReviewFlag.LOW_CONFIDENCE`
- Items needing review are tracked in `case.metadata["items_needing_review"]`

## Output Files

After full processing:
- `case.json` - Serialized Case object
- `reports/case_report.docx` - Word document
- `reports/case_report.pdf` - PDF with Bates numbering
- `reports/evidence_inventory.csv` - Evidence catalog
- `reports/timeline.txt` - Chronological events
- `reports/key_statements.txt` - Flagged statements
- `transcripts/*.txt` - Plain text transcripts
- `transcripts/*.srt` - Subtitle files
