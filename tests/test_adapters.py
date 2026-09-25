import unittest

from cloud_data_finops.adapters.aws import collect_commitment_coverage, collect_cost_metadata, collect_resource_utilization, collect_tag_costs
from cloud_data_finops.adapters.gcp import collect_job_metadata, collect_reservation_metadata
from tests.helpers import job

PERIOD = {"start": "2026-08-02", "end": "2026-08-31"}


class GcpMetadataClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def run_query(self, sql: str, *, purpose: str, page_token: str | None) -> dict:
        self.requests.append((purpose, sql))
        return {"rows": [job("metadata-only")] if purpose == "jobs" else [], "next_page_token": None}

    def read_table_content(self, *_: object) -> None:
        raise AssertionError("collector must not request business table content")


class AwsCostClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict]] = []

    def call(self, operation: str, request: dict, *, page_token: str | None) -> dict:
        self.requests.append((operation, request))
        rows = [{"service": "Amazon Athena", "region": "us-east-1", "cost_usd": 10.0, "baseline_usd": 5.0}]
        return {"rows": rows if request.get("GroupBy", [{}])[0].get("Type") == "DIMENSION" else [], "next_page_token": None}

    def query_cur(self, *_: object) -> None:
        raise AssertionError("collector must not query CUR when it is disabled")


class MetadataAdapterTests(unittest.TestCase):
    def test_gcp_collector_queries_only_metadata_views(self) -> None:
        client = GcpMetadataClient()

        jobs = collect_job_metadata({"project_id": "demo-project", "location": "eu"}, PERIOD, client)
        collect_reservation_metadata({"project_id": "demo-project"}, PERIOD, client)

        self.assertEqual([purpose for purpose, _ in client.requests], ["jobs", "reservations"])
        self.assertIn("region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT", client.requests[0][1])
        self.assertIn("INFORMATION_SCHEMA.RESERVATIONS_TIMELINE", client.requests[1][1])
        self.assertEqual(jobs[0]["job_id"], "metadata-only")

    def test_gcp_collector_requires_a_project(self) -> None:
        with self.assertRaisesRegex(ValueError, "project_id"):
            collect_job_metadata({}, PERIOD, GcpMetadataClient())

    def test_aws_collector_requests_only_cost_explorer_when_cur_is_disabled(self) -> None:
        client = AwsCostClient()

        costs = collect_cost_metadata({"account_alias": "demo-account", "cur": {"enabled": False}}, PERIOD, client)

        self.assertEqual([operation for operation, _ in client.requests], ["GetCostAndUsage"])
        self.assertEqual(client.requests[0][1]["GroupBy"], [{"Type": "DIMENSION", "Key": "SERVICE"}, {"Type": "DIMENSION", "Key": "REGION"}])
        self.assertEqual(costs[0]["service"], "Amazon Athena")

    def test_optional_aws_telemetry_is_collected_only_when_approved(self) -> None:
        client = AwsCostClient()
        scope = {"account_alias": "demo-account", "optional_telemetry": []}

        self.assertEqual(collect_resource_utilization(scope, PERIOD, client), [])
        self.assertEqual(collect_commitment_coverage(scope, PERIOD, client), [])
        self.assertEqual(collect_tag_costs(scope, PERIOD, client), [])
        self.assertEqual(client.requests, [])

        collect_tag_costs({**scope, "cost_allocation_tag": "team"}, PERIOD, client)
        self.assertEqual(client.requests[0][1]["GroupBy"], [{"Type": "TAG", "Key": "team"}])


if __name__ == "__main__":
    unittest.main()
