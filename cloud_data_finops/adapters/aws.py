from __future__ import annotations

from typing import Any, Protocol


class AwsCostExplorerClient(Protocol):
    def get_cost_and_usage(self, account_alias: str) -> list[dict[str, Any]]:
        """Return aggregated cost metadata for the approved account scope."""


def collect_cost_metadata(scope: dict[str, Any], client: AwsCostExplorerClient) -> list[dict[str, Any]]:
    account_alias = scope.get("account_alias")
    if not isinstance(account_alias, str) or not account_alias:
        raise ValueError("AWS account_alias is required for metadata collection")
    cur = scope.get("cur", {})
    if cur.get("enabled"):
        prefix = cur.get("approved_s3_prefix")
        if not isinstance(prefix, str) or not prefix:
            raise ValueError("AWS CUR collection requires an approved_s3_prefix")
        raise NotImplementedError("CUR collection is not implemented in the fixture-first release")
    return client.get_cost_and_usage(account_alias)

