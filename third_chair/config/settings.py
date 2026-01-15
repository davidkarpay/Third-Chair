"""Configuration settings for Third Chair."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# NOTE: load_dotenv() is called in CLI main.py for faster module imports
# from dotenv import load_dotenv
# load_dotenv()


@dataclass
class WhisperConfig:
    """Configuration for Whisper transcription."""

    model_size: str = "medium"
    device: str = "cpu"  # CPU-only for Intel UHD 630
    compute_type: str = "int8"  # Optimized for CPU
    beam_size: int = 5
    language: str = "en"
    vad_filter: bool = True
    cache_dir: Optional[str] = None


@dataclass
class DiarizationConfig:
    """Configuration for speaker diarization."""

    model_name: str = "pyannote/speaker-diarization-3.1"
    hf_token: Optional[str] = field(
        default_factory=lambda: os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
    )
    enabled: bool = True
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None


@dataclass
class OllamaConfig:
    """Configuration for Ollama LLM integration."""

    base_url: str = "http://localhost:11434"
    translation_model: str = "aya-expanse:8b"
    summary_model: str = "llama3.2:latest"
    vision_model: str = "qwen2.5vl:3b"
    timeout: int = 120  # Seconds - CPU inference is slow
    max_retries: int = 3


@dataclass
class VisionConfig:
    """Configuration for vision model analysis."""

    enabled: bool = True
    model: str = "qwen2.5vl:3b"
    timeout: int = 120
    temperature: float = 0.3
    max_image_size: int = 1024  # Max dimension for resizing


@dataclass
class TranslationConfig:
    """Configuration for translation."""

    source_lang: str = "es"
    target_lang: str = "en"
    min_words_for_translation: int = 5
    confidence_threshold: float = 0.5


@dataclass
class OutputConfig:
    """Configuration for output generation."""

    bates_prefix: str = "DEF"
    bates_start: int = 1
    include_timestamps: bool = True
    consolidate_segments: bool = True
    max_segment_gap: float = 3.0
    max_segment_length: int = 200


@dataclass
class Settings:
    """Main settings container."""

    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    diarization: DiarizationConfig = field(default_factory=DiarizationConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)

    # Paths
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "third_chair")
    places_file: Optional[Path] = None

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        settings = cls()

        # Override from environment
        if model := os.getenv("WHISPER_MODEL"):
            settings.whisper.model_size = model

        if device := os.getenv("WHISPER_DEVICE"):
            settings.whisper.device = device

        if url := os.getenv("OLLAMA_BASE_URL"):
            settings.ollama.base_url = url

        if model := os.getenv("OLLAMA_TRANSLATION_MODEL"):
            settings.ollama.translation_model = model

        if model := os.getenv("OLLAMA_SUMMARY_MODEL"):
            settings.ollama.summary_model = model

        if model := os.getenv("OLLAMA_VISION_MODEL"):
            settings.ollama.vision_model = model
            settings.vision.model = model

        if os.getenv("VISION_ENABLED", "").lower() == "false":
            settings.vision.enabled = False

        if output_dir := os.getenv("THIRD_CHAIR_OUTPUT_DIR"):
            settings.output_dir = Path(output_dir)

        if places_file := os.getenv("THIRD_CHAIR_PLACES_FILE"):
            settings.places_file = Path(places_file)

        if log_level := os.getenv("LOG_LEVEL"):
            settings.log_level = log_level

        return settings


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def configure(settings: Settings) -> None:
    """Set the global settings instance."""
    global _settings
    _settings = settings
