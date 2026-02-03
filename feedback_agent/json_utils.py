import json
import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


def fix_json_string(json_str: str) -> str:
    """
    Fix common JSON formatting issues.

    Handles:
    - Trailing commas before closing braces/brackets
    - Multiple consecutive commas
    """
    import re

    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    json_str = re.sub(r',\s*,', r',', json_str)
    return json_str


def parse_json_payload(payload: str, field_name: str) -> Optional[Dict[str, Any]]:
    """
    Parse a JSON payload with basic cleanup and fallback extraction.

    Args:
        payload: Raw JSON string (may include minor formatting issues)
        field_name: Field name for logging context

    Returns:
        Parsed JSON object, or None if parsing fails
    """
    if not payload:
        return None

    candidates = [payload, fix_json_string(payload)]
    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            continue

    start = payload.find("{")
    end = payload.rfind("}") + 1
    if start != -1 and end != -1:
        try:
            result = json.loads(fix_json_string(payload[start:end]))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse JSON for field '%s'", field_name)
    return None
