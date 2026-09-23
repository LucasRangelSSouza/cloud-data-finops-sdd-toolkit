# Read-only access plan

The toolkit reads cost, usage, job, and resource metadata. It does not read business-table contents, write cloud resources, change commitments, or submit purchases.

## GCP baseline

For `INFORMATION_SCHEMA.JOBS`, request `roles/bigquery.user` and `roles/bigquery.resourceViewer` at the assessed project. Google documents those roles for querying the view. A billing-export dataset reader is a separate, optional request. It is needed only when the approved assessment requires line-item billing data.

The tool rejects `roles/owner` and `roles/editor`. A live adapter must also reject an unapproved billing-export dataset before it sends a query.

## AWS baseline

For Cost Explorer, request only the actions required by the assessment, including `ce:GetCostAndUsage` and `ce:GetDimensionValues`. A CUR or Data Exports path requires separate approval for a named Athena workgroup, Glue metadata, an exact S3 report prefix, and a query-results location.

The tool rejects `AdministratorAccess`, wildcard actions, unrestricted Athena actions, and unrestricted S3 actions. The live adapter must reject any S3 prefix that is outside the approved scope.

## References

- [BigQuery JOBS access requirements](https://cloud.google.com/bigquery/docs/information-schema-jobs)
- [Cloud Billing access control](https://cloud.google.com/billing/docs/access-control)
- [AWS Cost Explorer authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_ce.html)
- [Athena IAM guidance](https://docs.aws.amazon.com/athena/latest/ug/security-iam-athena.html)

