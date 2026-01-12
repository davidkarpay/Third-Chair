# Third Chair - AI Assistant Instructions

## Project Overview

Third Chair is a legal discovery processing tool for Axon body-worn camera evidence packages. It transcribes audio/video, detects and translates Spanish content, and generates attorney-ready reports.

## Architecture

```
third_chair/
├── config/         # Configuration settings
├── ingest/         # ZIP extraction, file classification
├── transcription/  # Whisper transcription, diarization
├── translation/    # Ollama translation, language detection
├── witnesses/      # Witness management
├── documents/      # PDF/DOCX processing
├── summarization/  # AI summaries via Ollama
├── reports/        # Report generation
├── models/         # Data models (Case, Evidence, Transcript, Witness)
└── cli/            # Typer CLI interface
```

## Key Files

- `third_chair/cli/main.py` - CLI entry point
- `third_chair/models/case.py` - Main Case data model
- `third_chair/ingest/__init__.py` - Evidence ingestion pipeline
- `third_chair/transcription/__init__.py` - Transcription pipeline
- `third_chair/translation/__init__.py` - Translation pipeline

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
- `faster-whisper` - Transcription
- `pyannote.audio` - Speaker diarization
- `httpx` - Ollama API client
- `typer` + `rich` - CLI
- `pdfplumber` - PDF extraction
- `python-docx` - Word documents

## Hardware Constraints

This project is designed for CPU-only inference:
- Intel UHD 630 iGPU (no CUDA)
- Ollama runs one model at a time to avoid CPU thrashing
- Whisper uses int8 compute type for CPU optimization

## Common Tasks

### Adding a new file type
1. Add extension to `third_chair/models/evidence.py:FILE_TYPE_MAP`
2. Add content type pattern to `third_chair/ingest/file_classifier.py`

### Adding a new CLI command
1. Add function with `@app.command()` in `third_chair/cli/main.py`
2. Import any needed modules at function level (for lazy loading)

### Modifying translation prompts
Edit `_build_translation_prompt()` in `third_chair/translation/ollama_translator.py`

## Data Flow

1. **Ingest**: ZIP → Extract → Classify → Case object with EvidenceItems
2. **Transcribe**: Media → FFmpeg normalize → Whisper → Diarize → Transcript
3. **Translate**: Transcript → Language detect → Ollama translate → Updated Transcript
4. **Report**: Case → Evidence inventory → Witness list → Attorney report
