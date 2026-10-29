<spec>
$spec
</spec>

<stack>
$stack
</stack>

<nfr_plan>
$nfr_plan
</nfr_plan>

<allowed_dependencies>
$dependencies
</allowed_dependencies>

<review_feedback>
$feedback
</review_feedback>

Design the service for the MVP requirements:
1. modules: components/packages with their responsibility and the requirement IDs they implement.
2. openapi_yaml: a complete OpenAPI 3.0.3 document in YAML for every business endpoint: paths,
   parameters, request/response schemas, and every status code each operation can return.
   Error responses use media type application/problem+json with a schema containing type, title,
   status and detail. Do NOT include operational endpoints (/metrics, /health); the platform adds
   them. Redirect responses document the Location header.
3. schema_sql: SQLite DDL (CREATE TABLE / CREATE INDEX statements only) for the data model.
4. flows: the steps of each primary request flow.
5. error_model: how errors map to status codes and problem+json.
6. traceability: one row per MVP requirement (FR and NFR) listing the endpoints that realize it
   (format "METHOD /path" exactly as in the OpenAPI paths; empty for NFRs realized by the
   platform such as metrics), the modules, and the catalog IDs.
7. dependencies: the dependency coordinates you need, chosen ONLY from allowed_dependencies.
Keep the design to the minimum needed to satisfy the MVP requirements.
If review_feedback is present, address every item and keep everything else unchanged.
