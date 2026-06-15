"""JSON reporter — machine-readable output."""

import json
from typing import Any


class JSONReporter:
    """Outputs analysis results as JSON."""

    def render_all(self, results: dict[str, Any]) -> str:
        """Return JSON string of results."""
        # Make results JSON-serializable (convert sets to lists)
        cleaned = self._clean(results)
        return json.dumps(cleaned, indent=2, ensure_ascii=False, default=str)

    def _clean(self, obj: Any) -> Any:
        """Recursively clean non-serializable objects."""
        if isinstance(obj, dict):
            return {k: self._clean(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean(item) for item in obj]
        elif isinstance(obj, set):
            return sorted(obj)
        return obj
