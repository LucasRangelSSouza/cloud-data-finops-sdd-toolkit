import unittest

from cloud_data_finops.adapters.aws import collect_cost_metadata
from cloud_data_finops.adapters.gcp import collect_job_metadata


class GcpMetadataClient:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def list_jobs(self, project_id: str) -> list[dict[str, object]]:
        self.requests.append(f"jobs:{project_id}")
        return [{"job_id": "metadata-only", "bytes_billed": 1, "partition_pruned": True}]

    def read_table_content(self, *_: object) -> None:
        raise AssertionError("collector must not request business table content")


class AwsCostClient:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def get_cost_and_usage(self, account_alias: str) -> list[dict[str, object]]:
        self.requests.append(f"cost:{account_alias}")
        return [{"service": "Amazon Athena", "region": "us-east-1", "cost_usd": 10.0, "baseline_usd": 5.0}]

    def query_cur(self, *_: object) -> None:
        raise AssertionError("collector must not query CUR when it is disabled")


class MetadataAdapterTests(unittest.TestCase):
    def test_gcp_collector_requests_only_job_metadata(self) -> None:
        client = GcpMetadataClient()

        jobs = collect_job_metadata({"project_id": "demo-project"}, client)

        self.assertEqual(client.requests, ["jobs:demo-project"])
        self.assertEqual(jobs[0]["job_id"], "metadata-only")

    def test_aws_collector_requests_only_cost_explorer_when_cur_is_disabled(self) -> None:
        client = AwsCostClient()

        costs = collect_cost_metadata({"account_alias": "demo-account", "cur": {"enabled": False}}, client)

        self.assertEqual(client.requests, ["cost:demo-account"])
        self.assertEqual(costs[0]["service"], "Amazon Athena")


if __name__ == "__main__":
    unittest.main()
