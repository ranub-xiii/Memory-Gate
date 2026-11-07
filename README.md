# Memory Gate

A small, single-user reference service that retrieves scoped memory, validates its provenance and freshness, authorizes an exact model request, and records auditable outcomes before and after inference.

This repository contains only the Memory Gate implementation and its direct dependencies/tests extracted from the verified upstream snapshot of `xiiitore/authoritylab`. The upstream repository is preserved separately and is not modified by this repository.

## Scope

- Fail-closed pre-inference admission using an HMAC-SHA256 token bound to the exact outbound request and memory snapshot.
- Read-only Notion memory retrieval with bounded pagination, context size, subject scoping, and failure handling.
- A text-only OpenAI Responses API adapter with a fixed request shape, server-selected model, bounded output, and `store=false`.
- A single-user HTTP service with bearer authentication, mandatory idempotency keys, SQLite-backed request state, and durable audit logging.
- Unit and mocked-HTTP tests for the components above.

## Important limitations

This is an experimental reference implementation, not a production-certified memory platform.

- The signed token currently has no durable single-use nonce/replay store. A valid token may be replayed within its validity window if the host exposes a path to do so.
- The Notion adapter reads configured data sources and pages; relevance ranking, selective retrieval, and caching are not implemented.
- Tests mock Notion and OpenAI HTTP interactions. Live credentials, live retrieval, live inference, model availability, and billing have not been verified.
- `store=false` is not a Zero Data Retention guarantee. OpenAI abuse-monitoring retention settings are separate.
- The HTTP server defaults to loopback and speaks plain HTTP. Do not expose it directly to the public internet; use a trusted TLS-terminating edge.
- The service is single-user and text-only. It does not provide a UI, streaming, attachments, external tools, or conversation chaining.
- Every model invocation must pass through the controlled host. This library cannot prevent a separate caller from bypassing it and invoking a provider directly.

## Install and test

Python 3.11 or newer:

```bash
python -m pip install -e ".[test]"
python -m compileall -q authoritylab tests
python -m unittest discover -s tests -v
pytest -q
```

## Runtime configuration

The HTTP entry point is `authoritylab.server`. Configuration is read from environment variables; see [Architecture](docs/ARCHITECTURE.md) and [Security](SECURITY.md). Never commit API keys, Notion integration tokens, signing keys, client tokens, or live user memory.

No live secrets are included in this repository.

## Evidence and provenance

The extracted source snapshot is identified in [Source provenance](docs/SOURCE_PROVENANCE.md). The upstream snapshot's CI passed on Python 3.11, 3.12, and 3.13. That result is not a substitute for the CI run on this curated repository; this branch's own checks must pass before it is considered verified.
