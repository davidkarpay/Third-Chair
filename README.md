# Third Chair

Legal discovery processing tool for Axon evidence packages. Third Chair extracts, transcribes, translates, and organizes evidence from body-worn camera exports, creating comprehensive reports for attorneys.

## Features

- **Evidence Ingestion**: Extract and classify files from Axon ZIP exports
- **Transcription**: CPU-optimized Whisper transcription with speaker diarization
- **Translation**: Spanish/English translation via local Ollama (aya-expanse:8b)
- **Language Detection**: Automatic detection of Spanish content and code-switching
- **Witness Management**: Track and organize witnesses across evidence items
- **Document Processing**: OCR for scanned PDFs and images
- **AI Summarization**: Generate case summaries, timelines, and key findings
- **Report Generation**: Create attorney-ready reports with Bates numbering

## Requirements

- Python 3.10+
- FFmpeg (for audio/video processing)
- Ollama (for translation and summarization)
- Tesseract OCR (optional, for scanned documents)
- HuggingFace token (optional, for speaker diarization)

## Installation

```bash
# Clone the repository
git clone https://github.com/davidkarpay/Third-Chair.git
cd Third-Chair

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Install Tesseract (Ubuntu/Debian)
sudo apt-get install tesseract-ocr

# Install FFmpeg (Ubuntu/Debian)
sudo apt-get install ffmpeg

# Start Ollama and pull models
ollama serve
ollama pull aya-expanse:8b
ollama pull mistral:7b
```

## Quick Start

```bash
# Process an Axon evidence package (full pipeline)
third-chair process case_export.zip --output ./my_case

# Or step by step:
third-chair ingest case_export.zip --output ./my_case
third-chair transcribe ./my_case
third-chair translate ./my_case
third-chair documents ./my_case
third-chair summarize ./my_case
third-chair report ./my_case --format all
```

## Commands

| Command | Description |
|---------|-------------|
| `process` | Full pipeline: ingest, transcribe, translate, summarize, report |
| `ingest` | Extract and classify evidence from ZIP |
| `transcribe` | Transcribe audio/video files |
| `translate` | Translate Spanish content |
| `documents` | Process PDFs, Word docs, and images |
| `summarize` | Generate AI summaries and timeline |
| `witnesses` | Manage witnesses (import, rename, match) |
| `report` | Generate attorney reports (DOCX, PDF) |
| `info` | Show ZIP contents without extracting |
| `status` | Show processing status of a case |

### Process Command Options

```bash
third-chair process case.zip \
    --output ./my_case \
    --court-case "50-2025-CF-001234" \
    --skip-transcription \      # Skip audio/video transcription
    --skip-translation \        # Skip Spanish translation
    --skip-summarization \      # Skip AI summarization
    --no-diarization            # Disable speaker diarization
```

### Report Command Options

```bash
third-chair report ./my_case \
    --format all \              # docx, pdf, text, or all
    --bates-prefix DEF \        # Bates number prefix
    --bates-start 1 \           # Starting Bates number
    --prepared-by "John Doe" \  # Report preparer name
    --include-transcripts       # Include full transcripts
```

### Witness Command Options

```bash
# Import witness list from file
third-chair witnesses ./my_case --import witness_list.pdf

# List all witnesses
third-chair witnesses ./my_case --list

# Rename a speaker
third-chair witnesses ./my_case --rename "SPEAKER_1=Officer John Smith"

# Suggest names for unnamed speakers
third-chair witnesses ./my_case --suggest
```

## Configuration

Third Chair uses environment variables for configuration:

```bash
# Whisper transcription
WHISPER_MODEL=medium          # tiny, base, small, medium, large
WHISPER_DEVICE=cpu            # cpu, cuda, mps
WHISPER_COMPUTE_TYPE=int8     # float32, float16, int8

# Ollama settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TRANSLATION_MODEL=aya-expanse:8b
OLLAMA_SUMMARY_MODEL=mistral:7b

# Speaker diarization (optional)
HF_TOKEN=hf_xxx               # HuggingFace token for pyannote

# Output settings
OUTPUT_FORMAT=docx            # docx, pdf, text
BATES_PREFIX=DEF              # Default Bates prefix
```

## Output Structure

```
case_output/
├── case.json                 # Full case data with metadata
├── extracted/                # Raw extracted files
│   ├── videos/
│   ├── audio/
│   ├── documents/
│   └── images/
├── transcripts/              # Generated transcripts
│   ├── evidence_001.txt      # Plain text
│   ├── evidence_001.srt      # Subtitles
│   └── evidence_001.json     # Structured data
├── summaries/
│   └── case_summary.txt      # Executive summary
├── reports/
│   ├── case_report.docx      # Word document
│   ├── case_report.pdf       # PDF with Bates numbering
│   ├── evidence_inventory.csv
│   ├── witness_list.txt
│   ├── timeline.txt
│   └── key_statements.txt
└── review/
    └── low_confidence.json   # Items needing human review
```

## Supported File Types

### Media Files
- Video: .mp4, .avi, .mov, .mkv, .wmv, .webm
- Audio: .mp3, .wav, .m4a, .ogg, .flac, .aac

### Documents
- PDF (text-based and scanned via OCR)
- Word documents (.docx, .doc)
- Excel spreadsheets (.xlsx, .xls)
- Plain text (.txt)
- Images with text (.jpg, .png, .tiff, .bmp)

### Axon-Specific
- Table_of_Contents.xlsx
- Axon transcript documents (.docx)
- Body camera video exports

## Hardware Requirements

Third Chair is optimized for CPU-only inference:

- **Transcription**: ~2-3x realtime (10 min video = 20-30 min processing)
- **Translation**: ~2 seconds per segment via Ollama
- **Summarization**: ~5-10 seconds per summary
- **Memory**: 8GB+ RAM recommended (16GB for large models)

### Performance Tips

1. Use `medium` Whisper model for best quality/speed balance
2. Run only one Ollama model at a time to avoid CPU thrashing
3. Use `--skip-diarization` if speaker labels aren't needed
4. Process cases in batches during off-hours

## Module Overview

```
third_chair/
├── config/          # Configuration management
├── ingest/          # Evidence intake and classification
├── transcription/   # Audio/video transcription
├── translation/     # Language detection and translation
├── witnesses/       # Witness management
├── documents/       # Document processing (PDF, DOCX, OCR)
├── summarization/   # AI summaries and timeline
├── reports/         # Report generation (DOCX, PDF)
├── models/          # Data models (Case, Evidence, Transcript)
├── cli/             # Command-line interface
└── utils/           # Logging, hashing, place names
```

## License

MIT License

## Related Projects

- [Axon Transcript Translator](https://github.com/davidkarpay/spanish_translator_nllb_diarization) - Spanish/English transcript translation

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Support

For issues or feature requests, please [open an issue](https://github.com/davidkarpay/Third-Chair/issues).
