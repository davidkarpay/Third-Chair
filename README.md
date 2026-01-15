# Third Chair

Third Chair is a legal discovery processing tool designed for defense attorneys working with Axon body-worn camera evidence packages. The application extracts, transcribes, translates, and organizes evidence from law enforcement exports, generating comprehensive attorney-ready reports with Bates numbering.

## Features

- **Evidence Ingestion**: Extract and classify files from Axon ZIP exports automatically
- **Transcription**: CPU-optimized Whisper transcription with speaker diarization
- **Translation**: Spanish/English translation via local Ollama (aya-expanse:8b)
- **Language Detection**: Automatic detection of Spanish content and code-switching
- **Witness Management**: Track and organize witnesses across evidence items
- **Document Processing**: OCR for scanned PDFs and images
- **AI Summarization**: Generate case summaries, timelines, and key findings
- **Report Generation**: Create attorney-ready reports with Bates numbering
- **Proposition Analysis**: Skanda Framework for evidence-backed legal proposition evaluation
- **Interactive Research**: Chat interface and TUI for case exploration
- **Staging Area**: Drop-folder workflow for batch ZIP import with preview
- **Case Encryption**: AES-256 vault protection for sensitive case data

## Requirements

- Python 3.10 or higher
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

# Install system dependencies (Ubuntu/Debian)
sudo apt-get install tesseract-ocr ffmpeg

# Start Ollama and pull required models
ollama serve
ollama pull aya-expanse:8b
ollama pull mistral:7b
```

### Windows Support

Third Chair runs on both Windows (native) and WSL. Python 3.10+ on Windows is fully supported.

**Note:** For best performance on Windows without GPU, the application uses CPU-optimized inference.

## Quick Start

### Graphical Interface

Launch the terminal-based graphical interface to browse cases and research evidence:

```bash
third-chair tui
```

The TUI provides:
- Case selection from available processed cases
- Directory tree navigation (left panel)
- Interactive research chat (right panel)

### Command Line Processing

Process an Axon evidence package through the complete pipeline:

```bash
# Full pipeline processing
third-chair process case_export.zip --output ./my_case

# Step-by-step processing
third-chair ingest case_export.zip --output ./my_case
third-chair transcribe ./my_case
third-chair translate ./my_case
third-chair documents ./my_case
third-chair summarize ./my_case
third-chair extract-propositions ./my_case
third-chair report ./my_case --format all
```

### Research Chat

Query case evidence using natural language:

```bash
# Interactive chat session
third-chair chat ./my_case

# Single query mode
third-chair chat ./my_case --query "search knife"
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `tui` | Launch graphical interface with case selection and research chat |
| `process` | Full pipeline: ingest, transcribe, translate, summarize, report |
| `ingest` | Extract and classify evidence from ZIP |
| `transcribe` | Transcribe audio/video files |
| `translate` | Translate Spanish content |
| `documents` | Process PDFs, Word documents, and images |
| `summarize` | Generate AI summaries and timeline |
| `extract-propositions` | Extract legal propositions using Skanda Framework |
| `witnesses` | Manage witnesses (import, rename, match) |
| `report` | Generate attorney reports (DOCX, PDF) |
| `vision` | Analyze evidence photos using vision AI |
| `viewing-guide` | Generate recommended viewing timestamps |
| `sync-timeline` | Build synchronized multi-camera timeline |
| `chat` | Interactive research assistant |
| `info` | Display ZIP contents without extracting |
| `status` | Display processing status of a case |
| `version` | Display version information |
| `vault-init` | Initialize encryption vault on a case |
| `vault-unlock` | Unlock encrypted case for processing |
| `vault-lock` | Lock encrypted case |
| `vault-status` | Show vault encryption status |
| `vault-export` | Export decrypted copy of case |
| `vault-rotate` | Change vault password |
| `vault-verify` | Verify vault integrity |

### TUI Command

```bash
# Launch with case selection
third-chair tui

# Open specific case directly
third-chair tui /path/to/case

# Search additional path for cases
third-chair tui --search-path /mnt/d/cases
```

Keyboard shortcuts:
- Tab: Switch between directory tree and chat panels
- s: Open staging screen (import ZIPs)
- Q: Quit application
- ?: Display help

### Process Command Options

```bash
third-chair process case.zip \
    --output ./my_case \
    --court-case "50-2025-CF-001234" \
    --skip-transcription \
    --skip-translation \
    --skip-summarization \
    --no-diarization
```

### Report Command Options

```bash
third-chair report ./my_case \
    --format all \
    --bates-prefix DEF \
    --bates-start 1 \
    --prepared-by "John Doe" \
    --include-transcripts
```

### Extract Propositions Command

```bash
third-chair extract-propositions ./my_case \
    --issue self_defense \
    --proponent Defense \
    --min-confidence 0.5 \
    --include-timeline
```

### Witness Management

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

### Vision Analysis

Analyze evidence photos using vision AI (requires qwen2.5vl:3b model):

```bash
# Analyze all images in the case
third-chair vision ./my_case --all

# Analyze a specific image
third-chair vision ./my_case --image evidence_photo.jpg

# Use specialized prompt type
third-chair vision ./my_case --image photo.jpg --type injury

# Available prompt types: general, scene, injury, property, vehicle, document
```

### Viewing Guide

Generate recommended video timestamps for quick review:

```bash
# Generate viewing guide with all flagged moments
third-chair viewing-guide ./my_case

# Filter by specific flags
third-chair viewing-guide ./my_case --flags THREAT_KEYWORD,VIOLENCE_KEYWORD

# Custom output path
third-chair viewing-guide ./my_case --output ./review_timestamps.txt
```

### Sync Timeline Command

Synchronize events across multiple body cameras using UTC watermark timestamps:

```bash
# Extract timestamps from video watermarks and build synchronized timeline
third-chair sync-timeline ./my_case --extract-watermarks

# Force re-extraction even if timestamps exist
third-chair sync-timeline ./my_case --extract-watermarks --force

# Export synchronized timeline to JSON
third-chair sync-timeline ./my_case --output timeline.json
```

The synchronized timeline:
- Extracts UTC timestamps from Axon body camera watermarks using OCR
- Correlates events across multiple camera views by their synchronized time
- Shows which cameras were recording at each event's timestamp
- Provides relative timecodes for each camera (e.g., "Event at 2:15 into Camera A, 0:00 into Camera B")

### Chat Commands

When using the chat interface (`third-chair chat` or within TUI):

| Command | Description |
|---------|-------------|
| `search <query>` | Search transcripts for keywords |
| `threats` | Display statements flagged as threats |
| `violence` | Display statements flagged as violence |
| `witnesses` | List all witnesses |
| `case` | Display case information |
| `timeline` | Display timeline of events |
| `sync-timeline` | Display synchronized multi-camera timeline |
| `propositions` | List extracted propositions |
| `who said <quote>` | Find speaker of a specific quote |
| `tools` | List all available tools |
| `help` | Display command help |

### Staging Area

Import multiple Axon ZIP files using a drop-folder workflow:

```bash
# Create staging directory structure
mkdir -p staging/incoming

# Drop ZIP files into staging/incoming/
# Then launch TUI and press 's' to open staging screen
third-chair tui
```

Staging workflow:
1. Drop ZIP files into `staging/incoming/`
2. Press `s` in TUI to open staging screen
3. Select a ZIP to preview (file counts, case ID, agency)
4. Press `Enter` to process selected ZIP
5. Processed cases move to `cases/` directory

Directory structure:
```
staging/
├── incoming/    # Drop ZIPs here
├── processing/  # Currently being ingested
└── failed/      # Failed imports with error logs
cases/           # Successfully imported cases
```

### Case Encryption (Vault)

Protect sensitive case data with AES-256 encryption:

```bash
# Initialize vault on existing case
third-chair vault-init ./my_case

# Check vault status
third-chair vault-status ./my_case

# Unlock vault for processing
third-chair vault-unlock ./my_case

# Lock vault when done
third-chair vault-lock ./my_case

# Export decrypted copy
third-chair vault-export ./my_case --output ./export/

# Rotate password
third-chair vault-rotate ./my_case
```

Vault features:
- AES-256-GCM encryption for large files (streaming)
- Fernet encryption for small files (case.json, config)
- PBKDF2-HMAC-SHA256 key derivation (480,000 iterations)
- Session management with configurable timeout
- Transparent encryption/decryption during processing
- TUI password dialog integration

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
    case.json                 # Complete case data with metadata
    extracted/                # Raw extracted files
        (video, audio, document, and image files)
    transcripts/              # Generated transcripts
        evidence_001.txt      # Plain text transcript
        evidence_001.srt      # Subtitle file
        evidence_001.json     # Structured transcript data
    summaries/
        case_summary.txt      # Executive summary
    reports/
        case_report.docx      # Word document report
        case_report.pdf       # PDF with Bates numbering
        evidence_inventory.csv
        witness_list.txt
        timeline.txt
        key_statements.txt
        viewing_guide.txt     # Recommended video timestamps
    review/
        low_confidence.json   # Items requiring human review
```

## Skanda Framework

Third Chair implements the Skanda Framework for legal proposition evaluation. This framework treats "fact" as an earned output label rather than a stored boolean value.

### Key Concepts

- **Proposition**: An assertion that may be advanced at trial, with associated evidence
- **Proposit**: An atomic, testable mini-proposition backed by specific evidence references
- **Skanda**: A basket (collection) of proposits supporting or undermining a proposition
- **Evaluation Snapshot**: Computed values (holds/fails/uncertain, weight, probative value)

### Evaluation Process

1. Proposits are extracted from flagged transcript segments, key statements, and timeline events
2. Each proposit undergoes deterministic tests (personal knowledge, transcript confidence, corroboration)
3. Propositions are evaluated based on supporting vs. undermining proposit scores
4. Results indicate whether a proposition "holds under scrutiny" with associated weight

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

- **Transcription**: Approximately 2-3x realtime (10 minute video requires 20-30 minutes processing)
- **Translation**: Approximately 2 seconds per segment via Ollama
- **Summarization**: Approximately 5-10 seconds per summary
- **Memory**: 8GB RAM minimum, 16GB recommended for large models

### Performance Recommendations

1. Use the `medium` Whisper model for optimal quality/speed balance
2. Run only one Ollama model at a time to prevent CPU resource contention
3. Use `--skip-diarization` when speaker labels are not required
4. Process cases in batches during off-hours for large evidence packages

## Module Structure

```
third_chair/
    cli/             # Command-line interface
    config/          # Configuration management
    ingest/          # Evidence intake and classification
    staging/         # ZIP import staging area
    transcription/   # Audio/video transcription
    translation/     # Language detection and translation
    witnesses/       # Witness management
    documents/       # Document processing (PDF, DOCX, OCR, frame extraction)
    summarization/   # AI summaries, timeline, multi-camera sync
    analysis/        # Proposition extraction and evaluation
    reports/         # Report generation (DOCX, PDF)
    chat/            # Research assistant tools
    tui/             # Terminal user interface
    vault/           # Case encryption (AES-256)
    models/          # Data models (Case, Evidence, Transcript, Proposition)
    utils/           # Logging, hashing, place names
```

## License

MIT License

## Support

For issues or feature requests, please open an issue at:
https://github.com/davidkarpay/Third-Chair/issues
