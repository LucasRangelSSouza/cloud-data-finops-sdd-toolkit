from __future__ import annotations

from typing import Any, Protocol


class GcpJobMetadataClient(Protocol):
    def list_jobs(self, project_id: str) -> list[dict[str, Any]]:
        """Return job metadata without returning table content or query text."""


def collect_job_metadata(scope: dict[str, Any], client: GcpJobMetadataClient) -> list[dict[str, Any]]:
    project_id = scope.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("GCP project_id is required for metadata collection")
    return client.list_jobs(project_id)
