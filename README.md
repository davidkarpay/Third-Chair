# Third Chair

Legal discovery processing tool for Axon evidence packages. Third Chair extracts, transcribes, translates, and organizes evidence from body-worn camera exports, creating comprehensive reports for attorneys.

## Features

- **Evidence Ingestion**: Extract and classify files from Axon ZIP exports
- **Transcription**: CPU-optimized Whisper transcription with speaker diarization
- **Translation**: Spanish/English translation via local Ollama (aya-expanse:8b)
- **Language Detection**: Automatic detection of Spanish content and code-switching
- **Witness Management**: Track and organize witnesses across evidence items
- **Report Generation**: Create attorney-ready case reports with evidence inventories

## Requirements

- Python 3.10+
- FFmpeg (for audio/video processing)
- Ollama (for translation and summarization)
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
```

## Quick Start

```bash
# Process an Axon evidence package
third-chair process case_export.zip --output ./my_case

# Or step by step:
third-chair ingest case_export.zip --output ./my_case
third-chair transcribe ./my_case
third-chair translate ./my_case
```

## Commands

| Command | Description |
|---------|-------------|
| `process` | Full pipeline: ingest, transcribe, translate |
| `ingest` | Extract and classify evidence from ZIP |
| `transcribe` | Transcribe audio/video files |
| `translate` | Translate Spanish content |
| `info` | Show ZIP contents without extracting |
| `status` | Show processing status of a case |

## Configuration

Third Chair uses environment variables for configuration:

```bash
# Whisper transcription
WHISPER_MODEL=medium          # tiny, base, small, medium, large
WHISPER_DEVICE=cpu            # cpu, cuda, mps

# Ollama translation
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TRANSLATION_MODEL=aya-expanse:8b
OLLAMA_SUMMARY_MODEL=mistral:7b

# Speaker diarization (optional)
HF_TOKEN=hf_xxx               # HuggingFace token for pyannote
```

## Output Structure

```
case_output/
├── case.json                 # Full case data
├── extracted/                # Raw extracted files
├── transcripts/              # Generated transcripts
├── summaries/                # AI-generated summaries
├── reports/                  # Attorney reports
└── review/                   # Items needing review
```

## Hardware Requirements

Third Chair is optimized for CPU-only inference:

- **Transcription**: ~2-3x realtime (10 min video = 20-30 min processing)
- **Translation**: ~2 seconds per segment via Ollama
- **Memory**: 8GB+ RAM recommended

## License

MIT License

## Related Projects

- [Axon Transcript Translator](https://github.com/davidkarpay/spanish_translator_nllb_diarization) - Spanish/English transcript translation
