"""LLM-based embedding generation using Ollama."""

import struct
from pathlib import Path
from typing import Optional

import httpx

from ..config import get_workbench_config
from ..database import get_workbench_db


class Embedder:
    """Generates embeddings for text using Ollama's embedding API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        """Initialize the embedder.

        Args:
            base_url: Ollama API URL (default from config)
            model: Embedding model to use (default from config)
            timeout: Request timeout in seconds
        """
        config = get_workbench_config()

        self.base_url = base_url or config.ollama_base_url
        self.model = model or config.embedding_model
        self.timeout = timeout

        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def is_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = self._client.get(f"{self.base_url}/api/version")
            return response.status_code == 200
        except Exception:
            return False

    def is_model_available(self) -> bool:
        """Check if the embedding model is available."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return self.model in models or self.model.split(":")[0] in [
                    m.split(":")[0] for m in models
                ]
        except Exception:
            pass
        return False

    def embed_text(self, text: str) -> Optional[list[float]]:
        """Generate an embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None on error
        """
        try:
            response = self._client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            return data.get("embedding")

        except Exception:
            return None

    def embed_texts_batch(
        self,
        texts: list[str],
        progress_callback: Optional[callable] = None,
    ) -> list[Optional[list[float]]]:
        """Generate embeddings for multiple texts.

        Note: Ollama doesn't support batch embeddings, so this calls
        the API sequentially for each text.

        Args:
            texts: List of texts to embed
            progress_callback: Optional callback(current, total) for progress

        Returns:
            List of embeddings (None for any that failed)
        """
        results: list[Optional[list[float]]] = []
        total = len(texts)

        for i, text in enumerate(texts):
            if progress_callback:
                progress_callback(i + 1, total)

            embedding = self.embed_text(text)
            results.append(embedding)

        return results


def _floats_to_bytes(floats: list[float]) -> bytes:
    """Convert list of floats to bytes (float32 little-endian)."""
    return struct.pack(f"<{len(floats)}f", *floats)


def embed_extractions(
    case_dir: Path,
    model: Optional[str] = None,
    show_progress: bool = True,
) -> int:
    """Generate embeddings for all extractions in a case.

    Args:
        case_dir: Path to the case directory
        model: Optional model override
        show_progress: Whether to show progress output

    Returns:
        Number of embeddings created
    """
    config = get_workbench_config()

    # Initialize database
    db = get_workbench_db(case_dir)
    if not db.is_initialized():
        raise RuntimeError("Workbench not initialized. Run 'workbench init' first.")

    # Create embedder
    embedder = Embedder(model=model)

    if not embedder.is_available():
        raise RuntimeError("Ollama is not available. Please ensure it is running.")

    if not embedder.is_model_available():
        raise RuntimeError(
            f"Embedding model '{embedder.model}' not found. "
            f"Pull it with: ollama pull {embedder.model}"
        )

    # Get all extractions
    extractions = db.get_extractions()

    if not extractions:
        if show_progress:
            print("No extractions found. Run 'workbench extract' first.")
        return 0

    # Filter to extractions without embeddings
    extractions_to_embed = [e for e in extractions if not db.has_embedding(e.id)]

    if not extractions_to_embed:
        if show_progress:
            print("All extractions already have embeddings.")
        return 0

    if show_progress:
        try:
            from rich.console import Console
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

            console = Console()
            console.print(
                f"Generating embeddings for {len(extractions_to_embed)} extractions..."
            )
        except ImportError:
            console = None

    # Generate embeddings
    embeddings_batch: list[tuple[str, bytes]] = []
    created_count = 0

    for i, extraction in enumerate(extractions_to_embed):
        if show_progress and console and (i + 1) % 10 == 0:
            console.print(f"  Progress: {i + 1}/{len(extractions_to_embed)}")

        embedding = embedder.embed_text(extraction.content)

        if embedding:
            vector_bytes = _floats_to_bytes(embedding)
            embeddings_batch.append((extraction.id, vector_bytes))
            created_count += 1

            # Batch insert every 50 embeddings
            if len(embeddings_batch) >= 50:
                db.add_embeddings_batch(embeddings_batch, model=embedder.model)
                embeddings_batch = []

    # Insert remaining embeddings
    if embeddings_batch:
        db.add_embeddings_batch(embeddings_batch, model=embedder.model)

    embedder.close()
    db.close()

    if show_progress and console:
        console.print(f"Created {created_count} embeddings")

    return created_count
