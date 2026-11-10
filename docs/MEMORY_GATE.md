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
- `memory_gate_core/notion_memory_provider.py`: read-only Notion adapter with bounded 429/5xx/network retries, metadata-first retrieval with a recency fallback for body-only matches, ranked bounded snapshot construction.
- `memory_gate_core/retrieval.py`: deterministic lexical ranking, English/Croatian historical-intent recognition and stop words, source-aware status/type labelling, future-record rejection, and active supersession filtering. Relation endpoints are resolved only against `Memory Archive` records, matching the Notion relation data source's declared scope; unresolved, ambiguous, and conflicting edges remain visible as warnings.
- `memory_gate_core/openai_responses_client.py`: constrained Responses API adapter.
- `memory_gate_core/memory_gate_service.py`: orchestration, authentication, idempotency, and result classification.
- `memory_gate_core/idempotency.py`: persistent SQLite request claims and terminal state.
- `memory_gate_core/audit_log.py` and `privacy.py`: append-only audit records, integrity checks, and sensitive-data redaction.
- `memory_gate_core/server.py`: loopback-first HTTP entry point and environment-based construction.

## Security boundaries and known gaps

- The HMAC token binds the request digest, snapshot digest, policy version, subject/request identifiers, and source identifiers.
- The service wires token verification to SQLite nonce consumption. The nonce is hashed at rest and atomically inserted before outbound model access; a replay or nonce-store failure blocks the call. `MemoryGate.execute` now fails closed when no nonce consumer is configured and consumes the nonce before invoking its callback. `verify_token` remains non-consuming so the downstream OpenAI adapter can independently re-check the signature after the gate consumes it. Direct standalone calls to `OpenAIResponsesClient` outside the gated executor do not provide durable replay protection and must not be exposed as an alternate model entry point.
- The service is single-user. Subject identity is configured by the host, not selected by an untrusted client.
- Notion API access requires a separate server-side integration token with explicit access to every configured page and data source. A ChatGPT connector session is not inherited.
- Model credentials remain server-side. The client cannot select the model or add tools, streaming, arbitrary payload fields, or conversation chaining.
- The service defaults to `127.0.0.1`; the application server itself does not implement TLS, rate limiting, or edge-level denial-of-service protection.
- A successful gate decision proves only that configured policy checks passed. It does not prove retrieved memory is factually correct.
- Host deployment must ensure all model calls use this service. The library cannot enforce that boundary outside its own process.

## Deferred work

1. Semantic/vector retrieval evaluation against a labelled relevance set; current retrieval is deterministic lexical ranking, not embedding search.
2. Explicit valid-from/valid-until fields and richer temporal semantics; the current archive schema exposes creation/update timestamps and supersession fields, but no validity interval.
3. Live Notion and OpenAI integration tests in a controlled environment.
4. Deployment-level bypass, credential-isolation, TLS, rate-limit, and recovery tests.

## Install and test

The repository root installs both AuthorityLab and Memory Gate Core. Run `python -m unittest discover -s tests/memory_gate -v` and `pytest -q` after installing the project test extra.

This is an experimental reference implementation, not a production-certified memory platform. `store=false` is not a Zero Data Retention guarantee, and live provider behavior has not been verified by mocked unit tests.
