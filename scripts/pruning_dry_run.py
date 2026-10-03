"""Measure what partition pruning and column selection save, before changing anything, with BigQuery dry runs.

A dry run returns the bytes a query would process and costs nothing. This script runs the same question three ways
against a public partitioned table and prints the bytes for each:

  1. SELECT * with no partition filter (what BQ-001 and BQ-003 flag);
  2. only the needed columns, still no partition filter;
  3. only the needed columns, filtered on the partitioning column.

Requires google-cloud-bigquery and credentials for any project you can bill dry runs to (dry runs are free):

  pip install google-cloud-bigquery
  python scripts/pruning_dry_run.py --project YOUR_PROJECT

It is a demonstration for readers; it is not part of the fixture gate and it has not been run in this repository's CI.
"""

from __future__ import annotations

import argparse

TABLE = "bigquery-public-data.crypto_bitcoin.transactions"  # partitioned by block_timestamp_month
QUERIES = {
    "select *, no partition filter": f"SELECT * FROM `{TABLE}`",
    "3 columns, no partition filter": f"SELECT `hash`, block_timestamp, output_value FROM `{TABLE}`",
    "3 columns, one month": (f"SELECT `hash`, block_timestamp, output_value FROM `{TABLE}` WHERE block_timestamp_month = DATE '2024-01-01'"),
}


def main() -> None:
    from google.cloud import bigquery

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="project the dry runs are attributed to")
    args = parser.parse_args()
    client = bigquery.Client(project=args.project)
    config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    baseline = None
    for label, sql in QUERIES.items():
        processed = client.query(sql, job_config=config).total_bytes_processed
        baseline = baseline or processed
        print(f"{label:34s} {processed / 10**9:12.1f} GB  ({processed / baseline:6.1%} of the first query)")


if __name__ == "__main__":
    main()
