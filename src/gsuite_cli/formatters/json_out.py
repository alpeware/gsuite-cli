"""Deterministic JSON formatting for agent consumption."""

from __future__ import annotations

import datetime
import json
import sys
from typing import Any

from pydantic import BaseModel


def json_serial_fallback(obj: Any) -> Any:
    """Fallback serializer for objects that default JSON serializer cannot handle."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


def print_json(data: Any, indent: int = 2) -> None:
    """Print payload strictly as JSON to stdout."""
    output = json.dumps(data, indent=indent, default=json_serial_fallback)
    sys.stdout.write(output + "\n")
    sys.stdout.flush()
