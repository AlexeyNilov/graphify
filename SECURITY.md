# Security

Markdown contents are sent to the provider configured by `OPENAI_BASE_URL` when `grach build`
runs. With a loopback LM Studio URL they remain on the local machine; with a remote URL they leave
the machine. Do not include credentials, secrets, or documents the configured provider is not
permitted to receive.

OpenAPI files are parsed locally. YAML uses `yaml.safe_load`; arbitrary YAML object construction is
not enabled.

Grach reads supported files below the requested root and writes only to the configured graph
output path. Treat generated `graph.json` as sensitive because it can contain architecture names,
URLs, and relationships extracted from private documents.

Report vulnerabilities privately to the repository owner rather than opening a public issue.
