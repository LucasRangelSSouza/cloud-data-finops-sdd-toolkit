from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SpecificationError(ValueError):
    """Raised when an assessment specification cannot be evaluated safely."""


REQUIRED_TOP_LEVEL_FIELDS = {"schema_version", "assessment_id", "scope", "gcp", "aws"}


def load_specification(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SpecificationError(f"cannot read specification: {error}") from error
    except json.JSONDecodeError as error:
        raise SpecificationError(f"invalid JSON: {error.msg}") from error

    if not isinstance(payload, dict):
        raise SpecificationError("specification root must be an object")

    missing = sorted(REQUIRED_TOP_LEVEL_FIELDS - payload.keys())
    if missing:
        raise SpecificationError(f"missing required fields: {', '.join(missing)}")

    providers = payload["scope"].get("providers", [])
    if set(providers) != {"gcp", "aws"}:
        raise SpecificationError("scope.providers must contain exactly gcp and aws")

    if payload["scope"].get("allow_live_collection") is not False:
        raise SpecificationError("fixture mode requires allow_live_collection to be false")

    return payload

