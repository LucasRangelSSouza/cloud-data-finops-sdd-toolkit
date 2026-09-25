"""Response handling shared by provider adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..contracts import TelemetryContractError, validate_telemetry_rows

MAX_PAGES = 100
Page = dict[str, Any]


class AdapterResponseError(TelemetryContractError):
    """Raised when a provider response is incomplete or has an unexpected envelope."""


def collect_pages(operation: str, dataset: str, fetch: Callable[[str | None], Any]) -> list[dict[str, Any]]:
    """Follow page tokens until the provider reports completion, then validate every row.

    A response is treated as incomplete when the envelope is not an object, has
    no row list, repeats a page token, or keeps paging past MAX_PAGES.
    """
    rows: list[Any] = []
    seen_tokens: set[str] = set()
    token: str | None = None
    for _ in range(MAX_PAGES):
        page = fetch(token)
        if not isinstance(page, dict):
            raise AdapterResponseError(f"{operation}: response envelope must be an object")
        if "rows" not in page or not isinstance(page["rows"], list):
            raise AdapterResponseError(f"{operation}: incomplete response without a row list")
        next_token = page.get("next_page_token")
        if next_token is not None and (not isinstance(next_token, str) or not next_token):
            raise AdapterResponseError(f"{operation}: next_page_token must be null or a non-empty string")
        rows.extend(page["rows"])
        if next_token is None:
            return validate_telemetry_rows(dataset, rows)
        if next_token in seen_tokens:
            raise AdapterResponseError(f"{operation}: incomplete response, page token repeated")
        seen_tokens.add(next_token)
        token = next_token
    raise AdapterResponseError(f"{operation}: incomplete response, more than {MAX_PAGES} pages")
