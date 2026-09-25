"""Safety tests: adapter guards reject writes, business-table reads, unapproved datasets, S3 prefixes, and Athena paths."""

import unittest

from cloud_data_finops.adapters import aws as aws_adapter
from cloud_data_finops.adapters import gcp as gcp_adapter
from cloud_data_finops.safety import (
    AthenaApprovedScope,
    GcpApprovedScope,
    SafetyViolation,
    guard_athena_query,
    guard_aws_operation,
    guard_bigquery_query,
    guard_s3_uri,
)

GCP = GcpApprovedScope(project_id="demo-analytics", billing_export_dataset="billing_export")
GCP_NO_BILLING = GcpApprovedScope(project_id="demo-analytics")
ATHENA = AthenaApprovedScope(
    workgroup="finops-readonly",
    glue_database="cur_db",
    cur_table="cur_daily",
    cur_prefix="s3://demo-cost-reports/cur/daily/",
    query_results_prefix="s3://demo-athena-results/finops/",
)
PERIOD = {"start": "2026-08-02", "end": "2026-08-31"}
CUR_SCOPE = {
    "account_alias": "demo-data-account",
    "cur": {
        "enabled": True,
        "approved_s3_prefix": "s3://demo-cost-reports/cur/daily/",
        "athena_workgroup": "finops-readonly",
        "glue_database": "cur_db",
        "table": "cur_daily",
        "query_results_prefix": "s3://demo-athena-results/finops/",
    },
}


class BigQueryGuardTests(unittest.TestCase):
    def test_metadata_query_templates_pass(self) -> None:
        values = {"region": "region-us", **PERIOD}
        for template in (gcp_adapter.JOBS_QUERY, gcp_adapter.SCHEDULES_QUERY, gcp_adapter.RESERVATIONS_QUERY):
            guard_bigquery_query(template.format(**values), GCP_NO_BILLING)
        guard_bigquery_query(gcp_adapter.BILLING_QUERY.format(project="demo-analytics", dataset="billing_export", start="2026-08-02"), GCP)

    def test_rejects_write_and_ddl_statements(self) -> None:
        for sql in (
            "INSERT INTO `demo-analytics.sales.orders` VALUES (1)",
            "DELETE FROM `region-us.INFORMATION_SCHEMA.JOBS` WHERE TRUE",
            "SELECT 1; DROP TABLE `demo-analytics.sales.orders`",
            "CREATE TABLE `demo-analytics.tmp.copy` AS SELECT * FROM `region-us.INFORMATION_SCHEMA.JOBS`",
            "EXPORT DATA OPTIONS(uri='gs://x/*') AS SELECT * FROM `region-us.INFORMATION_SCHEMA.JOBS`",
            "WITH j AS (SELECT * FROM `region-us.INFORMATION_SCHEMA.JOBS`) SELECT * FROM j; MERGE t USING s ON TRUE",
        ):
            with self.assertRaises(SafetyViolation, msg=sql):
                guard_bigquery_query(sql, GCP)

    def test_rejects_business_table_extraction(self) -> None:
        for sql in (
            "SELECT * FROM `demo-analytics.sales.orders`",
            "SELECT j.job_id FROM `region-us.INFORMATION_SCHEMA.JOBS` j JOIN `demo-analytics.crm.customers` c ON TRUE",
            "SELECT * FROM `region-us.INFORMATION_SCHEMA.TABLES`",
            "SELECT * FROM `demo-analytics.billing_export.orders`",
        ):
            with self.assertRaises(SafetyViolation) as context:
                guard_bigquery_query(sql, GCP)
            self.assertNotIn("orders", str(context.exception))
            self.assertNotIn("customers", str(context.exception))

    def test_rejects_unapproved_billing_datasets(self) -> None:
        with self.assertRaisesRegex(SafetyViolation, "unapproved billing export dataset"):
            guard_bigquery_query("SELECT * FROM `demo-analytics.other_billing.gcp_billing_export_v1`", GCP)
        with self.assertRaisesRegex(SafetyViolation, "not approved"):
            guard_bigquery_query("SELECT * FROM `demo-analytics.billing_export.gcp_billing_export_v1`", GCP_NO_BILLING)

    def test_comments_cannot_hide_a_second_statement(self) -> None:
        guard_bigquery_query("SELECT job_id FROM `region-us.INFORMATION_SCHEMA.JOBS` -- ; DROP TABLE x", GCP)
        with self.assertRaises(SafetyViolation):
            guard_bigquery_query("SELECT job_id FROM `region-us.INFORMATION_SCHEMA.JOBS` /* x */; DROP TABLE x", GCP)

    def test_billing_collection_requires_an_approved_dataset(self) -> None:
        with self.assertRaisesRegex(ValueError, "approved billing_export_dataset"):
            gcp_adapter.collect_billing_costs({"project_id": "demo-analytics", "billing_export_dataset": None}, PERIOD, object())


class AwsGuardTests(unittest.TestCase):
    def test_rejects_write_operations(self) -> None:
        for operation in ("PutObject", "DeleteObject", "CreateAnomalyMonitor", "PurchaseReservedInstancesOffering", "UpdateCostCategoryDefinition"):
            with self.assertRaises(SafetyViolation):
                guard_aws_operation(operation)
        guard_aws_operation("GetCostAndUsage")

    def test_s3_locations_must_stay_inside_approved_prefixes(self) -> None:
        approved = ("s3://demo-cost-reports/cur/daily/",)
        guard_s3_uri("s3://demo-cost-reports/cur/daily/2026/08/part-0.parquet", approved)
        for uri in (
            "s3://demo-cost-reports/finance/ledger.csv",
            "s3://demo-cost-reports/cur/daily-other/x",
            "s3://demo-cost-reports/cur/daily/../../finance/x",
            "s3://other-bucket/cur/daily/x",
            "https://example.com/x",
        ):
            with self.assertRaises(SafetyViolation, msg=uri) as context:
                guard_s3_uri(uri, approved)
            self.assertNotIn("finance", str(context.exception))

    def test_athena_requires_the_approved_workgroup_results_prefix_and_table(self) -> None:
        sql = aws_adapter.CUR_QUERY.format(database="cur_db", table="cur_daily", **PERIOD)
        guard_athena_query(sql, "finops-readonly", "s3://demo-athena-results/finops/", ATHENA)
        cases = (
            (sql, "primary", "s3://demo-athena-results/finops/"),
            (sql, "", "s3://demo-athena-results/finops/"),
            (sql, "finops-readonly", "s3://demo-athena-results/other/"),
            ("SELECT * FROM sales_db.orders", "finops-readonly", "s3://demo-athena-results/finops/"),
            ("SELECT * FROM cur_db.cur_daily JOIN sales_db.orders ON TRUE", "finops-readonly", "s3://demo-athena-results/finops/"),
            ("UNLOAD (SELECT * FROM cur_db.cur_daily) TO 's3://x/'", "finops-readonly", "s3://demo-athena-results/finops/"),
            ("INSERT INTO cur_db.cur_daily SELECT 1", "finops-readonly", "s3://demo-athena-results/finops/"),
        )
        for query, workgroup, output in cases:
            with self.assertRaises(SafetyViolation, msg=(query, workgroup, output)):
                guard_athena_query(query, workgroup, output, ATHENA)

    def test_cur_collection_runs_one_guarded_aggregate_query(self) -> None:
        class RecordingAthena:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, str]] = []

            def run_query(self, sql: str, *, workgroup: str, output_location: str, page_token: str | None) -> dict:
                self.calls.append((sql, workgroup, output_location))
                return {"rows": [{"product_code": "AmazonAthena", "cost_usd": 1400.0}], "next_page_token": None}

        client = RecordingAthena()
        rows = aws_adapter.collect_cur_costs(CUR_SCOPE, PERIOD, client)
        self.assertEqual(rows, [{"product_code": "AmazonAthena", "cost_usd": 1400.0}])
        self.assertEqual(len(client.calls), 1)
        sql, workgroup, output = client.calls[0]
        self.assertIn("FROM cur_db.cur_daily", sql)
        self.assertEqual((workgroup, output), ("finops-readonly", "s3://demo-athena-results/finops/"))

    def test_cur_collection_refuses_an_incomplete_scope(self) -> None:
        scope = {"account_alias": "demo", "cur": {"enabled": True, "approved_s3_prefix": "s3://demo-cost-reports/cur/daily/"}}
        with self.assertRaisesRegex(ValueError, "athena_workgroup"):
            aws_adapter.collect_cur_costs(scope, PERIOD, object())

    def test_cur_collection_is_skipped_when_disabled(self) -> None:
        self.assertEqual(aws_adapter.collect_cur_costs({"account_alias": "demo", "cur": {"enabled": False}}, PERIOD, object()), [])


if __name__ == "__main__":
    unittest.main()
