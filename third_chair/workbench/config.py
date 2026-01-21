"""Configuration for the Evidence Workbench."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkbenchConfig:
    """Configuration settings for the workbench module."""

    # Extraction settings
    extraction_model: str = "mistral:7b"
    extraction_temperature: float = 0.3
    extraction_max_tokens: int = 2048

    # Embedding settings
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768  # nomic-embed-text dimension

    # Detection settings
    similarity_threshold: float = 0.7  # Minimum cosine similarity for clustering
    inconsistency_confidence_threshold: float = 0.6

    # LLM connection settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout: int = 180  # CPU inference can be slow

    # Database settings
    db_filename: str = "workbench.db"

    @classmethod
    def from_dict(cls, data: dict) -> "WorkbenchConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "extraction_model": self.extraction_model,
            "extraction_temperature": self.extraction_temperature,
            "extraction_max_tokens": self.extraction_max_tokens,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "similarity_threshold": self.similarity_threshold,
            "inconsistency_confidence_threshold": self.inconsistency_confidence_threshold,
            "ollama_base_url": self.ollama_base_url,
            "ollama_timeout": self.ollama_timeout,
            "db_filename": self.db_filename,
        }


# Default configuration
_config: Optional[WorkbenchConfig] = None


def get_workbench_config() -> WorkbenchConfig:
    """Get the global workbench configuration."""
    global _config
    if _config is None:
        _config = WorkbenchConfig()
    return _config


def set_workbench_config(config: WorkbenchConfig) -> None:
    """Set the global workbench configuration."""
    global _config
    _config = config
