# Memory Gate architecture

## Request path

1. The host accepts a user request and validates its shape and idempotency key.
2. `MemoryGateService` claims the idempotency key in SQLite.
3. `NotionMemoryProvider` retrieves a bounded, user-scoped memory snapshot from configured Notion sources.
4. The service constructs the exact outbound Responses API payload and binds a `GateRequest` to its digest.
5. `MemoryGate` validates subject scope, snapshot age/future skew, context size, and request/snapshot provenance. It creates a short-lived HMAC-SHA256 token.
6. A pre-invocation audit event must be written successfully before the model callback is invoked.
7. `OpenAIResponsesClient` recomputes the payload digest and verifies the token before network access.
8. The service records the terminal idempotency outcome and returns PASS, FAIL, BLOCKED, or UNKNOWN.

## Modules

- `memory_gate.py`: immutable request/snapshot structures, admission checks, signed token, and controlled execution.
- `notion_memory_provider.py`: read-only Notion API adapter and bounded snapshot construction.
- `openai_responses_client.py`: constrained Responses API adapter.
- `memory_gate_service.py`: orchestration, authentication, idempotency, and result classification.
- `idempotency.py`: persistent SQLite request claims and terminal state.
- `audit_log.py` and `privacy.py`: append-only audit records, integrity checks, and sensitive-data redaction.
- `server.py`: loopback-first HTTP entry point and environment-based construction.

## Security boundaries and known gaps

- The HMAC token binds the request digest, snapshot digest, policy version, subject/request identifiers, and source identifiers.
- The current nonce is an integrity-bound random identifier, not a durable single-use replay defense.
- The service is single-user. Subject identity is configured by the host, not selected by an untrusted client.
- Notion API access requires a separate server-side integration token with explicit access to every configured page and data source. A ChatGPT connector session is not inherited.
- Model credentials remain server-side. The client cannot select the model or add tools, streaming, arbitrary payload fields, or conversation chaining.
- The service defaults to `127.0.0.1`; the application server itself does not implement TLS, rate limiting, or edge-level denial-of-service protection.
- A successful gate decision proves only that configured policy checks passed. It does not prove the retrieved memory is factually correct.
- Host deployment must ensure all model calls use this service. The library cannot enforce that boundary outside its own process.

## Deferred work

1. Durable single-use nonce/replay prevention with atomic consumption.
2. Relevance-ranked retrieval over the Notion memory graph and explicit contradiction handling.
3. Temporal validity and supersession semantics in memory records.
4. Live Notion and OpenAI integration tests in a controlled environment.
5. Deployment-level bypass, credential-isolation, TLS, rate-limit, and recovery tests.
