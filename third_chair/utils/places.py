"""Place name preservation for translations.

Ensures place names (cities, streets, landmarks) are not translated.
This is important for legal documents where exact place names matter.
"""

import json
import re
from pathlib import Path
from typing import Optional, Set


# Default place names to preserve (Florida focus)
DEFAULT_PLACES = {
    # Florida cities
    "Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale",
    "St. Petersburg", "Hialeah", "Tallahassee", "Port St. Lucie",
    "Cape Coral", "Pembroke Pines", "Hollywood", "Miramar",
    "Gainesville", "Coral Springs", "Miami Gardens", "Clearwater",
    "Palm Bay", "Pompano Beach", "West Palm Beach", "Lakeland",
    "Davie", "Miami Beach", "Sunrise", "Boca Raton", "Deltona",
    "Plantation", "Deerfield Beach", "Fort Myers", "Melbourne",
    "Homestead", "Kissimmee", "Boynton Beach", "Lauderhill",
    "Weston", "Delray Beach", "Tamarac", "Palm Coast", "Margate",
    "Coconut Creek", "Sanford", "Doral", "North Port", "Ocala",

    # Florida counties
    "Miami-Dade", "Broward", "Palm Beach", "Hillsborough", "Orange",
    "Pinellas", "Duval", "Lee", "Polk", "Brevard", "Volusia",
    "Pasco", "Seminole", "Sarasota", "Manatee", "Collier",
    "Marion", "Lake", "Osceola", "Escambia", "St. Johns",

    # Common street names
    "Biscayne", "Flagler", "Collins", "Lincoln Road", "Ocean Drive",
    "Las Olas", "Sunrise Boulevard", "Commercial Boulevard",
    "Atlantic Avenue", "Glades Road", "Sample Road",

    # Landmarks
    "Everglades", "Florida Keys", "Key Biscayne", "Key West",
    "South Beach", "Downtown Miami", "Little Havana", "Wynwood",
    "Brickell", "Coral Gables", "Coconut Grove",
}

# Patterns that indicate a place name
PLACE_PATTERNS = [
    r"\b(?:North|South|East|West)\s+\d+(?:th|st|nd|rd)?\s+(?:Street|Avenue|Boulevard|Road)\b",
    r"\b\d+(?:th|st|nd|rd)?\s+(?:Street|Avenue|Boulevard|Road|Drive|Place|Lane)\b",
    r"\bInterstate\s+\d+\b",
    r"\bI-\d+\b",
    r"\bUS\s+\d+\b",
    r"\bState\s+Road\s+\d+\b",
    r"\bSR\s+\d+\b",
    r"\bFL\s+\d+\b",
]


class PlaceNamePreserver:
    """Preserves place names during translation."""

    def __init__(self, places_file: Optional[Path] = None):
        """
        Initialize with place names.

        Args:
            places_file: Optional JSON file with additional place names
        """
        self.places: Set[str] = DEFAULT_PLACES.copy()
        self._place_patterns = [re.compile(p, re.IGNORECASE) for p in PLACE_PATTERNS]

        if places_file and places_file.exists():
            self._load_places_file(places_file)

    def _load_places_file(self, path: Path) -> None:
        """Load additional places from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.places.update(data)
                elif isinstance(data, dict) and "places" in data:
                    self.places.update(data["places"])
        except Exception:
            pass  # Ignore errors loading places file

    def add_place(self, name: str) -> None:
        """Add a place name to preserve."""
        self.places.add(name)

    def add_places(self, names: list[str]) -> None:
        """Add multiple place names."""
        self.places.update(names)

    def find_places(self, text: str) -> list[str]:
        """
        Find place names in text.

        Args:
            text: Text to search

        Returns:
            List of found place names
        """
        found = []

        # Check for known places
        text_lower = text.lower()
        for place in self.places:
            if place.lower() in text_lower:
                found.append(place)

        # Check for patterns
        for pattern in self._place_patterns:
            matches = pattern.findall(text)
            found.extend(matches)

        return list(set(found))

    def protect_places(self, text: str) -> tuple[str, dict[str, str]]:
        """
        Replace place names with placeholders before translation.

        Args:
            text: Text to process

        Returns:
            Tuple of (protected text, mapping of placeholders to originals)
        """
        mapping = {}
        protected = text

        places_found = self.find_places(text)

        for i, place in enumerate(places_found):
            placeholder = f"__PLACE_{i}__"
            # Use word boundaries to avoid partial replacements
            pattern = re.compile(re.escape(place), re.IGNORECASE)
            protected = pattern.sub(placeholder, protected)
            mapping[placeholder] = place

        return protected, mapping

    def restore_places(self, text: str, mapping: dict[str, str]) -> str:
        """
        Restore place names after translation.

        Args:
            text: Translated text with placeholders
            mapping: Placeholder to original mapping

        Returns:
            Text with places restored
        """
        result = text

        for placeholder, original in mapping.items():
            result = result.replace(placeholder, original)

        return result


# Global instance
_preserver: Optional[PlaceNamePreserver] = None


def get_place_preserver() -> PlaceNamePreserver:
    """Get the global PlaceNamePreserver instance."""
    global _preserver
    if _preserver is None:
        # Try to load places.json from config directory
        config_path = Path(__file__).parent.parent / "config" / "places.json"
        _preserver = PlaceNamePreserver(places_file=config_path)
    return _preserver


def protect_places(text: str) -> tuple[str, dict[str, str]]:
    """Convenience function to protect places in text."""
    return get_place_preserver().protect_places(text)


def restore_places(text: str, mapping: dict[str, str]) -> str:
    """Convenience function to restore places in text."""
    return get_place_preserver().restore_places(text, mapping)
