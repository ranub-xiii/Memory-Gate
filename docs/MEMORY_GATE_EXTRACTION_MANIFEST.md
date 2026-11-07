# Memory Gate extraction manifest

## Source snapshot

- Repository: [xiiitore/authoritylab](https://github.com/xiiitore/authoritylab)
- Branch: `feat/memory-gate-preinference`
- Commit: `da2d02a99c92c54980f16628a8aebaddea998b2b`
- Tree: `132837fc39f439232a4bf802bc578f11cac589aa`

## Runtime modules

The following eight runtime modules were copied byte-for-byte from the source snapshot into `memory_gate_core/`. Their source blob SHAs are recorded below and match the copied blob IDs:

| Source | Destination | Blob SHA |
|---|---|---|
| `audit_log.py` | `memory_gate_core/audit_log.py` | `4b795a0908000fd87ae5881ee1131d5836ea8e89` |
| `idempotency.py` | `memory_gate_core/idempotency.py` | `9790a8aefb5c2bedfeba19335dd31f7fae760995` |
| `memory_gate.py` | `memory_gate_core/memory_gate.py` | `f5ab370467ed5b1025fa704acf50f1a4f74f8220` |
| `memory_gate_service.py` | `memory_gate_core/memory_gate_service.py` | `181bd3df22b547e5c53de8ab44309ff3024a8268` |
| `notion_memory_provider.py` | `memory_gate_core/notion_memory_provider.py` | `535caeb85e5bca2429501bf7800602573fc0e5d2` |
| `openai_responses_client.py` | `memory_gate_core/openai_responses_client.py` | `05774db58d1d3123c6db077c07acec4b6e31b331` |
| `privacy.py` | `memory_gate_core/privacy.py` | `cb7b53026e728a41732c36e9566d568b21128b4a` |
| `server.py` | `memory_gate_core/server.py` | `f827ca2c89757d2f1a1334bf17203b9057ff13d4` |

## Tests

Eight focused test modules are retained under `tests/memory_gate/`. Their imports were changed from the former `authoritylab.*` extraction path to `memory_gate_core.*` so they do not shadow or replace the existing AuthorityLab package. Test logic is otherwise carried forward from the verified extraction snapshot.

## Repository preservation

This extraction is additive. Existing AuthorityLab root modules, tests, documentation, package metadata, CodeQL workflow, Docker integration workflow, and Python CI workflow remain present. The new package is installed alongside the existing `authoritylab` package; it does not replace it.
