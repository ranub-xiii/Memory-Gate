# Security notes

- Treat Notion memory and model outputs as untrusted input.
- Keep `NOTION_API_KEY`, `OPENAI_API_KEY`, `MEMORY_GATE_SIGNING_KEY_B64`, `MEMORY_GATE_AUDIT_HMAC_KEY_B64`, and `MEMORY_GATE_CLIENT_TOKEN` in a server-side secret manager or protected environment only.
- Never commit secrets, raw memory exports, audit logs, SQLite databases, or production request payloads.
- Keep the HTTP listener on loopback unless a trusted TLS-terminating reverse proxy and network policy are configured.
- Use distinct gate-signing and audit-integrity keys.
- Review audit records for privacy before sharing them.
- Report security defects privately to the repository owner; do not publish exploit details before remediation.
