# Security

Markdown contents are sent to OpenAI when `graphify build` runs. Do not include credentials,
secrets, personal data, or documents that your OpenAI data policy does not permit.

OpenAPI files are parsed locally. YAML uses `yaml.safe_load`; arbitrary YAML object construction is
not enabled.

Graphify reads supported files below the requested root and writes only to the configured graph
output path. Treat generated `graph.json` as sensitive because it can contain architecture names,
URLs, and relationships extracted from private documents.

Report vulnerabilities privately to the repository owner rather than opening a public issue.
