"""Utilities to normalize/format MCP tool results.

FastMCP/Model Context Protocol tool calls may return structured content objects
(e.g. TextContent) which are not JSON serializable by default.

This module converts those objects into JSON-safe structures and provides a
human-readable text representation.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Iterable, List, Union


JsonSafe = Union[None, bool, int, float, str, List["JsonSafe"], Dict[str, "JsonSafe"]]


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def normalize_to_json_safe(value: Any, *, max_depth: int = 8) -> JsonSafe:
    """Best-effort conversion to JSON-serializable types.

    - primitives pass through
    - dict/list/tuple/set/iterables normalize recursively
    - pydantic models / dataclasses / objects with model_dump/dict are converted
    - unknown objects fall back to a small dict with repr
    """

    if max_depth <= 0:
        return str(value)

    if _is_primitive(value):
        return value  # type: ignore[return-value]

    if isinstance(value, dict):
        out: Dict[str, JsonSafe] = {}
        for k, v in value.items():
            out[str(k)] = normalize_to_json_safe(v, max_depth=max_depth - 1)
        return out

    if isinstance(value, (list, tuple, set)):
        return [normalize_to_json_safe(v, max_depth=max_depth - 1) for v in value]

    # Pydantic v2
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        try:
            return normalize_to_json_safe(value.model_dump(), max_depth=max_depth - 1)
        except Exception:
            pass

    # Pydantic v1 or common pattern
    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        try:
            return normalize_to_json_safe(value.dict(), max_depth=max_depth - 1)
        except Exception:
            pass

    if dataclasses.is_dataclass(value):
        try:
            return normalize_to_json_safe(dataclasses.asdict(value), max_depth=max_depth - 1)
        except Exception:
            pass

    # MCP content objects (TextContent, ImageContent, ResourceContent, etc.)
    # We avoid importing fastmcp/mcp types to keep this module decoupled.
    attr_candidates = [
        "type",
        "text",
        "mimeType",
        "mime_type",
        "uri",
        "name",
        "data",
        "annotations",
    ]
    extracted: Dict[str, JsonSafe] = {}
    for attr in attr_candidates:
        if hasattr(value, attr):
            try:
                extracted[attr] = normalize_to_json_safe(getattr(value, attr), max_depth=max_depth - 1)
            except Exception:
                continue

    if extracted:
        # Ensure we always include a type hint for debugging
        extracted.setdefault("__class__", value.__class__.__name__)
        return extracted

    # Iterable but not string/bytes: normalize a short list
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        try:
            return [normalize_to_json_safe(v, max_depth=max_depth - 1) for v in list(value)]
        except Exception:
            pass

    return {
        "__class__": value.__class__.__name__,
        "repr": repr(value),
    }


def extract_text(value: Any) -> str:
    """Extract a human readable string from MCP result content."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, dict):
        # Common MCP shapes: {"content": [...]} etc.
        if "text" in value and isinstance(value.get("text"), str):
            return value["text"]
        if "content" in value:
            return extract_text(value.get("content"))
        return str(value)

    if isinstance(value, (list, tuple)):
        parts: List[str] = []
        for item in value:
            t = extract_text(item)
            if t:
                parts.append(t)
        return "\n".join(parts)

    # MCP TextContent-like object
    if hasattr(value, "text"):
        try:
            t = getattr(value, "text")
            if isinstance(t, str):
                return t
        except Exception:
            pass

    return str(value)
