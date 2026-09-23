import unittest

from cloud_data_finops.policies import evaluate


def specification() -> dict:
    return {"gcp": {"jobs": []}, "aws": {"costs": [], "resources": []}}


class PolicyTests(unittest.TestCase):
    def test_detects_repeated_high_volume_query_pattern(self) -> None:
        payload = specification()
        payload["gcp"]["jobs"] = [
            {"job_id": "a", "bytes_billed": 600_000_000_000, "partition_pruned": True, "fingerprint": "same"},
            {"job_id": "b", "bytes_billed": 600_000_000_000, "partition_pruned": True, "fingerprint": "same"},
        ]
        self.assertIn("BQ-002", [item["id"] for item in evaluate(payload)])

    def test_detects_aws_region_cost_anomaly(self) -> None:
        payload = specification()
        payload["aws"]["costs"] = [{"service": "Amazon Athena", "region": "us-east-1", "cost_usd": 900, "baseline_usd": 300}]
        self.assertIn("AWS-001", [item["id"] for item in evaluate(payload)])

    def test_detects_idle_data_resource(self) -> None:
        payload = specification()
        payload["aws"]["resources"] = [{"resource_id": "workgroup-demo", "type": "athena-workgroup", "utilization": 0.05}]
        self.assertIn("AWS-002", [item["id"] for item in evaluate(payload)])


if __name__ == "__main__":
    unittest.main()
