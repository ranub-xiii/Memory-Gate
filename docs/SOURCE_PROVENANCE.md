# Source provenance

This repository is a curated extraction from the following immutable upstream snapshot:

- Repository: `https://github.com/xiiitore/authoritylab`
- Branch: `feat/memory-gate-preinference`
- Commit: `da2d02a99c92c54980f16628a8aebaddea998b2b`
- Git tree: `132837fc39f439232a4bf802bc578f11cac589aa`

The upstream branch was read-only during this extraction. The private `ranub-xiii/Memory-Gate` repository is separate.

## Included source modules

The following modules are copied byte-for-byte from the identified upstream commit:

- `memory_gate.py`
- `notion_memory_provider.py`
- `openai_responses_client.py`
- `memory_gate_service.py`
- `idempotency.py`
- `server.py`
- `audit_log.py`
- `privacy.py`

The corresponding test files are copied byte-for-byte:

- `test_memory_gate.py`
- `test_notion_memory_provider.py`
- `test_openai_responses_client.py`
- `test_memory_gate_service.py`
- `test_idempotency.py`
- `test_server.py`
- `test_audit_log.py`
- `test_audit_integration.py`
- `test_privacy.py`

The package initializer, packaging metadata, CI workflow, and documentation are specific to this curated repository. They are integration scaffolding and must be tested here independently.

No Termux MCP adapter, remote relay, general workflow engine, capability registry, sandbox runner, or unrelated AuthorityLab modules are included.
