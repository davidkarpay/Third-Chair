"""Vision model analyzer for evidence images.

Uses Ollama vision models (qwen2.5vl) to analyze photos for legal discovery,
detecting objects, people, damage, and generating scene descriptions.
"""

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image

from ..config.settings import get_settings


@dataclass
class VisionAnalysis:
    """Result of vision model analysis on an image."""

    description: str
    objects_detected: list[str] = field(default_factory=list)
    people_count: int = 0
    scene_type: str = ""
    damage_detected: bool = False
    weapons_detected: bool = False
    injuries_visible: bool = False
    key_findings: list[str] = field(default_factory=list)
    model: str = ""
    processing_time_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None


# Legal discovery prompts for different analysis types
LEGAL_PROMPTS = {
    "general": """Analyze this evidence photo for legal discovery purposes.
Describe:
1. What is visible in the scene (location, setting, objects)
2. Any people visible (count, positions, clothing, visible injuries)
3. Any weapons or potential weapons
4. Any visible damage to property or persons
5. Any text, signs, or documents visible
6. Anything else legally relevant

Be factual and objective. Do not speculate.""",

    "scene": """Describe this scene for a legal case.
Focus on: location type, lighting, time of day if discernible,
condition of the area, and any notable features.""",

    "injury": """Examine this image for any visible injuries or harm.
Describe: location on body, type of injury, severity if discernible,
and any visible medical attention.""",

    "property": """Analyze this image for property damage.
Describe: what is damaged, extent of damage, possible cause if evident.""",

    "vehicle": """Analyze this vehicle image.
Note: make/model if visible, damage locations, license plates,
any distinguishing features.""",

    "document": """Read and transcribe any text visible in this image.
Note the type of document and key information.""",
}


class VisionAnalyzer:
    """Analyzer for evidence images using Ollama vision models."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        Initialize vision analyzer.

        Args:
            model: Vision model to use (default: qwen2.5vl:3b)
            base_url: Ollama API URL (default from settings)
            timeout: Request timeout in seconds
        """
        settings = get_settings()

        self.model = model or getattr(
            settings.ollama, 'vision_model', 'qwen2.5vl:3b'
        )
        self.base_url = base_url or settings.ollama.base_url
        self.timeout = timeout

        self._client = httpx.Client(timeout=timeout)

    def is_available(self) -> bool:
        """Check if Ollama and vision model are available."""
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = [m["name"] for m in response.json().get("models", [])]
                return self.model in models
        except Exception:
            pass
        return False

    def _load_image_as_base64(self, image_path: Path) -> str:
        """Load an image file and convert to base64."""
        # Resize large images to reduce memory usage
        max_size = 1024

        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Resize if too large
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Save to bytes
            import io
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def analyze(
        self,
        image_path: Path,
        prompt: Optional[str] = None,
        prompt_type: str = "general",
    ) -> VisionAnalysis:
        """
        Analyze an image using the vision model.

        Args:
            image_path: Path to the image file
            prompt: Custom prompt (overrides prompt_type)
            prompt_type: Type of analysis (general, scene, injury, etc.)

        Returns:
            VisionAnalysis with description and detected elements
        """
        if not image_path.exists():
            return VisionAnalysis(
                description="",
                success=False,
                error=f"Image not found: {image_path}",
            )

        # Use custom prompt or get from templates
        analysis_prompt = prompt or LEGAL_PROMPTS.get(prompt_type, LEGAL_PROMPTS["general"])

        try:
            # Load and encode image
            image_base64 = self._load_image_as_base64(image_path)

            # Build request payload
            payload = {
                "model": self.model,
                "prompt": analysis_prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 1024,
                },
            }

            # Send request
            response = self._client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code != 200:
                return VisionAnalysis(
                    description="",
                    model=self.model,
                    success=False,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )

            data = response.json()
            raw_response = data.get("response", "").strip()
            duration_ms = data.get("total_duration", 0) / 1_000_000

            # Parse the response into structured data
            analysis = self._parse_response(raw_response)
            analysis.model = self.model
            analysis.processing_time_ms = duration_ms

            return analysis

        except httpx.TimeoutException:
            return VisionAnalysis(
                description="",
                model=self.model,
                success=False,
                error="Request timed out. Vision analysis may be slow on CPU.",
            )
        except Exception as e:
            return VisionAnalysis(
                description="",
                model=self.model,
                success=False,
                error=str(e),
            )

    def _parse_response(self, text: str) -> VisionAnalysis:
        """Parse vision model response into structured analysis."""
        analysis = VisionAnalysis(
            description=text,
            success=True,
        )

        text_lower = text.lower()

        # Detect weapons
        weapon_keywords = [
            'knife', 'gun', 'firearm', 'weapon', 'blade', 'hammer',
            'bat', 'crowbar', 'machete', 'pistol', 'rifle'
        ]
        analysis.weapons_detected = any(w in text_lower for w in weapon_keywords)

        # Detect injuries
        injury_keywords = [
            'blood', 'injury', 'wound', 'bruise', 'cut', 'bleeding',
            'laceration', 'swelling', 'burn', 'injured'
        ]
        analysis.injuries_visible = any(w in text_lower for w in injury_keywords)

        # Detect damage
        damage_keywords = [
            'damage', 'broken', 'shattered', 'dent', 'crack',
            'destroyed', 'vandalized', 'smashed'
        ]
        analysis.damage_detected = any(w in text_lower for w in damage_keywords)

        # Detect scene type
        if any(w in text_lower for w in ['indoor', 'inside', 'room', 'house', 'apartment']):
            analysis.scene_type = 'indoor'
        elif any(w in text_lower for w in ['outdoor', 'outside', 'street', 'parking']):
            analysis.scene_type = 'outdoor'
        elif any(w in text_lower for w in ['vehicle', 'car', 'truck']):
            analysis.scene_type = 'vehicle'

        # Try to detect people count from text
        import re
        people_patterns = [
            r'(\d+)\s*(?:people|persons|individuals)',
            r'(\d+)\s*(?:men|women|adults)',
            r'(one|two|three|four|five)\s*(?:people|person)',
        ]
        for pattern in people_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    num = match.group(1)
                    if num.isdigit():
                        analysis.people_count = int(num)
                    else:
                        word_to_num = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5}
                        analysis.people_count = word_to_num.get(num, 0)
                except Exception:
                    pass
                break

        # Extract key findings (sentences with important keywords)
        important_keywords = weapon_keywords + injury_keywords + damage_keywords + [
            'evidence', 'suspicious', 'notable', 'significant'
        ]
        sentences = text.replace('\n', ' ').split('. ')
        for sentence in sentences:
            if any(kw in sentence.lower() for kw in important_keywords):
                clean = sentence.strip()
                if clean and len(clean) > 10:
                    analysis.key_findings.append(clean[:200])

        return analysis

    def analyze_batch(
        self,
        image_paths: list[Path],
        prompt_type: str = "general",
        progress_callback=None,
    ) -> dict[str, VisionAnalysis]:
        """
        Analyze multiple images.

        Args:
            image_paths: List of image paths
            prompt_type: Type of analysis to perform
            progress_callback: Optional callback(current, total) for progress

        Returns:
            Dictionary mapping filename to VisionAnalysis
        """
        results = {}
        total = len(image_paths)

        for i, path in enumerate(image_paths):
            if progress_callback:
                progress_callback(i + 1, total)

            results[path.name] = self.analyze(path, prompt_type=prompt_type)

        return results

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# Global instance
_analyzer: Optional[VisionAnalyzer] = None


def get_vision_analyzer() -> VisionAnalyzer:
    """Get the global vision analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = VisionAnalyzer()
    return _analyzer


def check_vision_ready() -> tuple[bool, str]:
    """
    Check if vision analysis is ready.

    Returns:
        Tuple of (is_ready, message)
    """
    analyzer = get_vision_analyzer()

    if not analyzer.is_available():
        return False, f"Vision model {analyzer.model} not available. Pull with: ollama pull {analyzer.model}"

    return True, f"Vision model {analyzer.model} is ready"
