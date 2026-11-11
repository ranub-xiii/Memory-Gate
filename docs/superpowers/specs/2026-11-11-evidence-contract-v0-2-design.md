# Memory Gate Evidence and Relation Contract v0.2 — Design

Date: 2026-11-11
Status: Design accepted by project owner via instruction to proceed with the recommended approach.
Base: `ranub-xiii/Memory-Gate` PR #3 HEAD `7281a9bcab7d1dc7ad7fd821e46c8601af8bec6a`
Implementation branch: `feat/evidence-contract-v0-2`

## 1. Intent

Make provenance and semantic endpoint roles explicit, versioned, and fail-closed without adding another plugin, service, database, graph, or source registry. Repair extraction of the existing Notion `Memory Sources` URL property and define a machine-verifiable Evidence contract that binds a relation to a registered source, a precise locator, a content fingerprint, a scope, and explicit endpoint roles.

The objective is structural and provenance validation. A valid contract is not proof that a cited source is true, authoritative, or correctly interpreted.

## 2. Current state

Confirmed against PR #3 HEAD `7281a9b`:

- `NotionMemoryProvider` queries the configured data sources, including `Memory Sources`.
- `extract_page_properties()` handles title, rich text, select/status, multi-select, number, checkbox, date, timestamps, unique ID, and relation properties, but not Notion's `url` property type.
- The provider therefore drops URL values from source records.
- The existing provider test verifies that email and phone properties are ignored, but does not cover URL extraction.
- Integrity Contract v0.1 requires non-empty Evidence text; it explicitly does not resolve that text to a source or artifact.
- Memory Graph relation semantics already distinguish SUPPORTS, REFUTES, CONTRADICTS, SUPERSEDES, and DERIVED_FROM. Architecture/component relations such as USES, PART_OF, and TESTS are outside this graph contract.
- The Memory Sources schema contains Source (title), Source Type, Version (text), DOI (text), URL (Notion url), Publication Date and Notes. A read-only query on 2026-11-11 returned zero source records. Thus no Evidence source can currently resolve successfully until a human registers one; implementation must not seed the registry.

## 3. Goals

1. Extract Notion URL properties without changing extraction of existing property types.
2. Define a strict, versioned JSON Evidence envelope.
3. Require Evidence to reference one unique page in the existing Memory Sources data source.
4. Validate the registered source identifier and its available stable locator (HTTPS URL and/or DOI); never fetch arbitrary URLs during validation.
5. Bind Evidence to the exact relation endpoints and explicitly declared endpoint roles.
6. Validate role direction, scope compatibility, timestamps, locator shape, and content fingerprint format.
7. Keep validation deterministic, offline, testable, and fail-closed.
8. Preserve all legacy Notion rows and leave Architecture Graph semantics separate.

## 4. Non-goals and anti-goals

- No new plugin, source registry, database, graph, service, or Notion schema migration.
- No automatic conversion of legacy Evidence text into structured Evidence.
- No inference of endpoint roles from page titles, similarity, record Type, or relation names alone.
- No network fetch of source URLs, no live source scraping, and no claim that a hash proves truth.
- No automatic promotion of claims to VERIFIED/true.
- No reclassification of USES, PART_OF, TESTS, or other Architecture Graph relations as Memory Graph edges.
- No merge, publish, or changes to `main` as part of this work.

## 5. Approaches considered

### A. Minimal URL extraction only

Add support for Notion `url` properties and a regression test. This fixes data loss but leaves Evidence free text and endpoint semantics unverifiable.

### B. Staged, strict Evidence contract (selected)

Fix URL extraction, introduce a pure Evidence parser/validator, add relation-role and scope validation, then integrate the validator at the Memory Graph activation boundary. Legacy rows remain untouched and are classified as `LEGACY_UNVERIFIED`; they cannot gain v0.2 activation merely because they contain text. This is the smallest approach that closes the provenance gap while reusing the existing registry and graph.

### C. Notion schema migration

Add structured properties and migrate relation rows. Rejected for this iteration: the current registry and relations are not sufficiently normalized, migration would be destructive/high-risk, and no migration is needed to establish a versioned JSON contract inside the existing Evidence field.

## 6. Contract: Evidence v1

The Evidence property for a v0.2 Memory Graph relation contains one JSON object with the following logical shape:

```json
{
  "schema": "memory-gate.evidence.v1",
  "source_ref": "00000000-0000-4000-8000-000000000000",
  "locator": {
    "kind": "section",
    "value": "Methods / §2"
  },
  "observed_at": "2026-11-11T08:00:00Z",
  "source_version": "2026-11-10",
  "content_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "scope": {
    "from_scope_id": "stable-proposition-scope",
    "to_scope_id": "stable-proposition-scope",
    "description": "Curator-declared scope shared by the edge endpoints",
    "endpoint_ids": [
      "00000000-0000-4000-8000-000000000001",
      "00000000-0000-4000-8000-000000000002"
    ]
  },
  "validity": null,
  "endpoints": {
    "from_id": "00000000-0000-4000-8000-000000000001",
    "to_id": "00000000-0000-4000-8000-000000000002",
    "from_role": "EVIDENCE",
    "to_role": "CLAIM"
  }
}
```

The implementation must enforce exact top-level and nested key sets (no unknown keys), required non-empty strings, UUID syntax, timezone-aware RFC 3339 timestamps normalized to UTC, and a 64-character lowercase SHA-256 hex digest. The digest is defined over the exact captured artifact bytes, without text normalization. The current registry stores metadata, not immutable source snapshots, so the validator checks digest syntax only; it cannot independently recompute the digest unless the corresponding artifact bytes are separately supplied to a verifier. A syntactically valid digest is not verified provenance. `source_version` must exactly match the registered `Memory Sources.Version` value; it is null only when that registry field is empty. To preserve historical editions, each distinct registered edition can have its own Memory Sources page UUID even when editions share a DOI or URL. `scope.from_scope_id` and `scope.to_scope_id` are required non-empty identifiers (maximum 128 characters each). `scope.endpoint_ids` must contain exactly the two canonical relation endpoint UUIDs (sorted lexicographically); this binds the declared scope pair to the precise edge. The Evidence payload is limited to 16,384 UTF-8 bytes, locator values to 2,048 characters, and scope descriptions to 2,000 characters. `validity` is null for all relation types except SUPERSEDES, where it is an object containing exactly `from_valid_from` and `to_valid_from` timezone-aware RFC 3339 timestamps.

Allowed locator kinds are a deliberately small allowlist: `page`, `section`, `paragraph`, `timestamp`, `json_pointer`, and `artifact_offset`. A locator value must be non-empty and bounded in length. A raw URL is not a locator and cannot replace `source_ref`.

`source_ref` must resolve to exactly one Notion page in the already-configured `Memory Sources` data source. The registered record must expose at least one usable identifier: an absolute HTTPS URL or a syntactically valid DOI. URL validation rejects non-HTTPS schemes, credentials/userinfo, missing hostnames, and malformed URLs. DOI validation is syntax-only. No network request is made. The URL/DOI is taken from the registered page, never from the Evidence payload.

If the source registry is empty, the source reference is absent/ambiguous, the registry record has no usable URL/DOI, or Evidence source_version does not match the registered Version value, provenance resolution fails closed with a specific reason. The page UUID is the authoritative source identity. Multiple registered pages may legitimately share a DOI or URL (for example, editions or captures); this does not make a UUID reference ambiguous. Duplicate occurrences of the same page UUID in the resolution input are ambiguous and blocked. This is expected until a human adds and curates source records; this implementation must not create them.

## 7. Relation roles and invariants

The Evidence `endpoints` object must name the exact page UUIDs already present in the relation's From/To fields and declare both roles explicitly. The validator compares IDs; it does not infer roles from page titles or record Type.

| Relation | From role | To role | Additional invariant |
|---|---|---|---|
| SUPPORTS | EVIDENCE | CLAIM | `from_scope_id` and `to_scope_id` must be equal and non-empty |
| REFUTES | COUNTER_EVIDENCE | CLAIM | `from_scope_id` and `to_scope_id` must be equal and non-empty |
| CONTRADICTS | CLAIM | CLAIM | Both endpoint scope IDs must be equal and non-empty; relation remains symmetric |
| SUPERSEDES | NEWER_VERSION | OLDER_VERSION | Endpoint scope IDs must be equal and non-empty; `validity.from_valid_from` must be later than `validity.to_valid_from` |
| DERIVED_FROM | DERIVED_RECORD | SOURCE_RECORD | Endpoint scope IDs must be non-empty; they may differ; directed edge must remain acyclic |

The validator must compare `scope.endpoint_ids` with the canonical From/To UUIDs for every relation and apply the endpoint scope-pair rules in the table. The current Memory Archive schema has no structured Scope property, and From/To in Memory Relations are text properties. Therefore, the validator can check that the curator explicitly declared a consistent scope pair for the edge, but cannot independently compare those declarations with the semantic content or scope of the endpoint pages. This limitation must appear in validation results and documentation; scope consistency is not semantic proof.

The validator must not silently reinterpret unsupported relation types. `USES`, `PART_OF`, and `TESTS` remain Architecture Graph relations and are not accepted as Memory Graph relation kinds.

Role and scope validation is a curation contract: it verifies that the declared structure is internally consistent and matches relation endpoints. It does not prove that a record genuinely is evidence or a claim. No role may be inferred from a record's Type.

## 8. Legacy and activation behavior

- Plain-text, malformed JSON, unknown schema versions, and incomplete Evidence are classified as `LEGACY_UNVERIFIED` or `INVALID_EVIDENCE`, with a machine-readable reason.
- No legacy row is rewritten, migrated, or automatically promoted.
- A relation with legacy/unverified Evidence cannot satisfy the v0.2 activation predicate.
- The integration point must fail closed: only a relation whose existing identity/status/direction checks pass **and** whose v0.2 Evidence and role/scope validation pass can be treated as v0.2-valid.
- Preserve historical visibility and diagnostics; do not delete or rewrite records.
- The implementation must report separately: (a) structural validity, (b) registered-source resolution including source-version match, and (c) role/scope declaration consistency. Digest recalculation is a separate verification capability and remains unavailable from registry metadata alone. None of these statuses means the underlying claim is true or that the declared scope matches endpoint content.

## 9. Implementation boundaries

Expected files, subject to repository inspection before editing:

- `memory_gate_core/notion_memory_provider.py`: add URL extraction.
- `memory_gate_core/evidence.py`: strict parsing, schema versioning, source-reference validation helpers, typed validation results.
- `memory_gate_core/relation_validation.py`: relation-kind role matrix and scope/direction checks.
- Existing retrieval/resolver module: integrate the v0.2 activation predicate without weakening v0.1 identity, status, direction, or cycle checks.
- Focused tests under `tests/memory_gate/`.
- Update `docs/MEMORY_GATE_INTEGRITY_CONTRACT.md` to v0.2 only after implementation and tests establish the behavior.

Do not add dependencies unless the existing standard library and current project dependencies demonstrably cannot satisfy the contract. Prefer the existing test framework and standard-library parsing/validation.

## 10. Test requirements

Test-first sequence (each new behavior begins with a failing focused test):

1. URL property extraction: valid URL preserved; null/malformed values handled safely; existing unsupported private properties remain excluded.
2. Evidence parser: valid v1 object accepted; malformed JSON, duplicate keys, missing/extra keys, unsupported version, invalid UUID, invalid timestamp, invalid digest, malformed scope pair, conditional validity errors, oversized payload/locator rejected.
3. Source resolution: unique registered page UUID accepted; missing/duplicate page UUID blocked; empty registry blocked; HTTPS/DOI accepted; HTTP, credentials, unsafe schemes, malformed host/DOI rejected; source_version must exactly match registered Version. Same DOI/URL on distinct page UUIDs remains resolvable by UUID.
4. Endpoint binding: Evidence endpoint IDs must equal relation From/To IDs.
5. Role matrix: every supported relation accepts only its required role pair; wrong direction/role rejected.
6. Scope: SUPPORTS/REFUTES/CONTRADICTS/SUPERSEDES require equal non-empty declared from/to scope IDs; DERIVED_FROM requires both IDs but permits different scopes. The validator reports these as curator assertions because Memory Archive has no independent Scope property.
7. Temporal ordering: SUPERSEDES requires explicit ordered temporal values; missing or reversed values rejected.
8. Cycle behavior: DERIVED_FROM remains acyclic and does not alter existing cycle protections.
9. Legacy compatibility: plain-text Evidence remains untouched and is not treated as v0.2-valid.
10. Regression: all existing Memory Gate and AuthorityLab tests continue to pass.

Required verification targets: Python 3.11, 3.12, and 3.13; compile/lint; Docker integration and CodeQL where the repository workflows support them. Report each exact commit and run. No test result may be inferred from a prior commit.

## 11. Security and failure behavior

- Treat Notion property values and Evidence JSON as untrusted input.
- No URL fetching, shell execution, dynamic imports, or implicit network resolution in validators.
- Bound JSON input size, locator length, and string lengths.
- Reject duplicate JSON keys rather than accepting ambiguous payloads.
- Use explicit error codes/reasons; do not leak Notion tokens or private source contents.
- Fail closed on unknown schema versions, unknown relation types, unresolved source IDs, ambiguous endpoint IDs, and missing role/scope data.

## 12. Acceptance criteria

- URL extraction is covered by focused regression tests.
- Evidence v1 is parsed strictly and deterministically.
- A source reference is accepted only when it resolves uniquely in the existing Memory Sources data source, its registered URL/DOI is structurally valid, and Evidence source_version exactly matches the source page Version property (or both are empty/null).
- Relation endpoints and explicit roles match the relation row and role matrix.
- Scope endpoint IDs and temporal constraints are enforced for applicable relation types.
- Legacy free text remains unchanged and cannot acquire v0.2 validity automatically.
- Existing identity, direction, graph separation, cycle, and retrieval regression tests pass.
- No Notion schema/data mutations and no changes to `main`.
- Implementation is not declared complete until local test output and exact-commit CI evidence are independently verified.
