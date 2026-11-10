# Memory Gate architecture

## Request path

1. The host validates the request shape and idempotency key.
2. `MemoryGateService` claims the idempotency key in SQLite.
3. `NotionMemoryProvider` retrieves a bounded, user-scoped memory snapshot from configured Notion sources.
4. The service constructs the exact outbound Responses API payload and binds a `GateRequest` to its digest.
5. `MemoryGate` validates subject scope, snapshot age/future skew, context size, and request/snapshot provenance; it creates a short-lived HMAC-SHA256 token.
6. A pre-invocation audit event must be written successfully before the model callback is invoked.
7. `OpenAIResponsesClient` recomputes the payload digest and verifies the token before network access.
8. The service records the terminal idempotency outcome and returns PASS, FAIL, BLOCKED, or UNKNOWN.

## Package layout

- `memory_gate_core/memory_gate.py`: admission checks, request/snapshot structures, signed token, controlled execution.
- `memory_gate_core/notion_memory_provider.py`: read-only Notion adapter, metadata-first retrieval, ranked bounded snapshot construction.\n- `memory_gate_core/retrieval.py`: deterministic lexical ranking, evidence-status labelling, future-record rejection, supersession filtering, and explicit contradiction warnings.
- `memory_gate_core/openai_responses_client.py`: constrained Responses API adapter.
- `memory_gate_core/memory_gate_service.py`: orchestration, authentication, idempotency, and result classification.
- `memory_gate_core/idempotency.py`: persistent SQLite request claims and terminal state.
- `memory_gate_core/audit_log.py` and `privacy.py`: append-only audit records, integrity checks, and sensitive-data redaction.
- `memory_gate_core/server.py`: loopback-first HTTP entry point and environment-based construction.

## Security boundaries and known gaps

- The HMAC token binds the request digest, snapshot digest, policy version, subject/request identifiers, and source identifiers.
- The current nonce is an integrity-bound random identifier, not a durable single-use replay defense.
- The service is single-user. Subject identity is configured by the host, not selected by an untrusted client.
- Notion API access requires a separate server-side integration token with explicit access to every configured page and data source. A ChatGPT connector session is not inherited.
- Model credentials remain server-side. The client cannot select the model or add tools, streaming, arbitrary payload fields, or conversation chaining.
- The service defaults to `127.0.0.1`; the application server itself does not implement TLS, rate limiting, or edge-level denial-of-service protection.
- A successful gate decision proves only that configured policy checks passed. It does not prove retrieved memory is factually correct.
- Host deployment must ensure all model calls use this service. The library cannot enforce that boundary outside its own process.

## Deferred work

1. Durable single-use nonce/replay prevention with atomic consumption.
2. Relevance-ranked retrieval over the Notion memory graph and explicit contradiction handling.
3. Temporal validity and supersession semantics in memory records.
4. Live Notion and OpenAI integration tests in a controlled environment.
5. Deployment-level bypass, credential-isolation, TLS, rate-limit, and recovery tests.

## Install and test

The repository root installs both AuthorityLab and Memory Gate Core. Run `python -m unittest discover -s tests/memory_gate -v` and `pytest -q` after installing the project test extra.

This is an experimental reference implementation, not a production-certified memory platform. `store=false` is not a Zero Data Retention guarantee, and live provider behavior has not been verified by mocked unit tests.
