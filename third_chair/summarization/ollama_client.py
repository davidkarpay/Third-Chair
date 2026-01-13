"""Ollama API client for summarization.

Provides a wrapper around the Ollama API for generating summaries,
with rate limiting and error handling for CPU-bound inference.
"""

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from ..config.settings import get_settings


@dataclass
class OllamaResponse:
    """Response from Ollama API."""

    text: str
    model: str
    total_duration_ms: float = 0.0
    prompt_tokens: int = 0
    response_tokens: int = 0
    success: bool = True
    error: Optional[str] = None


class OllamaClient:
    """Client for interacting with Ollama API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama API URL (default from settings)
            model: Model to use (default from settings)
            timeout: Request timeout in seconds
        """
        settings = get_settings()

        self.base_url = base_url or settings.ollama.base_url
        self.model = model or settings.ollama.summary_model
        self.timeout = timeout

        self._client = httpx.Client(timeout=timeout)

    def is_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            response = self._client.get(f"{self.base_url}/api/version")
            return response.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """List available models."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def ensure_model_loaded(self, model: Optional[str] = None) -> bool:
        """
        Ensure a model is loaded (warm start).

        Args:
            model: Model name (default: self.model)

        Returns:
            True if model is ready
        """
        model = model or self.model

        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Hi",
                    "stream": False,
                    "options": {"num_predict": 1},
                },
                timeout=120.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> OllamaResponse:
        """
        Generate a response from Ollama.

        Args:
            prompt: The prompt to send
            system: Optional system prompt
            model: Model to use (default: self.model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            OllamaResponse with generated text
        """
        model = model or self.model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system:
            payload["system"] = system

        try:
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return OllamaResponse(
                    text="",
                    model=model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )

            data = response.json()

            return OllamaResponse(
                text=data.get("response", "").strip(),
                model=model,
                total_duration_ms=data.get("total_duration", 0) / 1_000_000,
                prompt_tokens=data.get("prompt_eval_count", 0),
                response_tokens=data.get("eval_count", 0),
                success=True,
            )

        except httpx.TimeoutException:
            return OllamaResponse(
                text="",
                model=model,
                success=False,
                error="Request timed out. Ollama may be overloaded.",
            )
        except Exception as e:
            return OllamaResponse(
                text="",
                model=model,
                success=False,
                error=str(e),
            )

    def summarize(
        self,
        text: str,
        max_length: int = 200,
        context: Optional[str] = None,
    ) -> OllamaResponse:
        """
        Generate a summary of text.

        Args:
            text: Text to summarize
            max_length: Approximate max words in summary
            context: Optional context about the content

        Returns:
            OllamaResponse with summary
        """
        system = """You are a legal assistant summarizing evidence for attorneys.
Be concise, factual, and focus on legally relevant details.
Do not add opinions or speculation."""

        prompt = f"""Summarize the following in approximately {max_length} words.
Focus on key facts, people involved, and significant statements.

"""
        if context:
            prompt += f"Context: {context}\n\n"

        prompt += f"Content:\n{text[:8000]}"  # Limit input size

        return self.generate(prompt, system=system, max_tokens=max_length * 2)

    def extract_key_points(
        self,
        text: str,
        num_points: int = 5,
    ) -> OllamaResponse:
        """
        Extract key points from text.

        Args:
            text: Text to analyze
            num_points: Number of key points to extract

        Returns:
            OllamaResponse with bullet points
        """
        system = """You are a legal assistant extracting key points from evidence.
Focus on facts that would be relevant in a legal proceeding."""

        prompt = f"""Extract the {num_points} most important points from this text.
Format as a numbered list.

Text:
{text[:8000]}"""

        return self.generate(prompt, system=system, max_tokens=500)

    def analyze_speakers(
        self,
        text: str,
    ) -> OllamaResponse:
        """
        Analyze speakers in a transcript.

        Args:
            text: Transcript text

        Returns:
            OllamaResponse with speaker analysis
        """
        system = """You are a legal assistant analyzing speakers in a transcript.
Identify roles (officer, victim, witness, etc.) based on their statements."""

        prompt = f"""Analyze the speakers in this transcript.
For each speaker, describe:
1. Their likely role
2. Key statements they made
3. Their demeanor (if discernible)

Transcript:
{text[:8000]}"""

        return self.generate(prompt, system=system, max_tokens=800)

    def unload_model(self, model: Optional[str] = None) -> None:
        """Unload a model to free memory."""
        model = model or self.model

        try:
            self._client.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "keep_alive": 0},
                timeout=10.0,
            )
        except Exception:
            pass

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# Global client instance
_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get the global Ollama client instance."""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def check_ollama_ready() -> tuple[bool, str]:
    """
    Check if Ollama is ready for summarization.

    Returns:
        Tuple of (is_ready, message)
    """
    client = get_ollama_client()

    if not client.is_available():
        return False, "Ollama is not running. Start with: ollama serve"

    models = client.list_models()
    settings = get_settings()

    if settings.ollama.summary_model not in models:
        return False, f"Model {settings.ollama.summary_model} not found. Pull with: ollama pull {settings.ollama.summary_model}"

    return True, "Ollama is ready"
