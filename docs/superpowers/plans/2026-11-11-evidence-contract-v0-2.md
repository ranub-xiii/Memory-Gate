# Memory Gate Evidence v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add strict, source-registered Evidence validation and explicit Memory Graph endpoint-role/scope checks while preserving legacy data and the existing graph separation.

**Architecture:** Keep Notion extraction in the existing provider. Put strict JSON parsing and registered-source resolution in a focused `evidence.py`; put relation role/scope rules in `relation_validation.py`; integrate the validator at the existing relation activation boundary in `retrieval.py`. No new service, registry, database, or Notion migration.

**Tech Stack:** Python >=3.11, standard library, existing unittest/pytest suite, current Notion provider.

**Spec:** `docs/superpowers/specs/2026-11-11-evidence-contract-v0-2-design.md`

## Global Constraints

- Python minimum: 3.11.
- Evidence schema identifier: `memory-gate.evidence.v1`.
- Registered source identity: Notion page UUID in the existing `Memory Sources` data source.
- Registered source version: exact string match between Evidence `source_version` and the source page's `Version` property; null only when the registry field is empty.
- Evidence payload limit: 16,384 UTF-8 bytes; locator value limit: 2,048 characters; scope description limit: 2,000 characters; each scope ID limit: 128 characters.
- Duplicate DOI/URL values across distinct source page UUIDs are permitted; duplicate occurrences of the same source page UUID in resolver input are ambiguous.
- Registered URL policy: absolute HTTPS only; reject credentials/userinfo and malformed hostnames; DOI syntax validation is offline.
- SHA-256 digest: exactly 64 lowercase hexadecimal characters.
- Timestamps: timezone-aware RFC 3339; normalize to UTC.
- Locator kinds: `page`, `section`, `paragraph`, `timestamp`, `json_pointer`, `artifact_offset`.
- Relation kinds: SUPPORTS, REFUTES, CONTRADICTS, SUPERSEDES, DERIVED_FROM only.
- Architecture relations such as USES, PART_OF, and TESTS remain outside Memory Graph.
- Legacy text is never rewritten or auto-promoted; legacy/unverified Evidence cannot satisfy v0.2 activation, so current plain-text Memory Graph edges will have no ordinary retrieval effect until curated.
- No network fetch, no new dependency unless proven necessary, no Notion writes, no changes to `main`, no merge or publish.

## Review Focus

- Duplicate JSON keys can make parsers disagree — test duplicate-key rejection in Task 2.
- An HTTPS URL with userinfo or an encoded unsafe scheme can bypass naive checks — test userinfo and malformed URL inputs in Task 2.
- The source registry can contain repeated DOI/URL metadata for distinct editions — verify lookup remains UUID-based and only duplicated page UUIDs are ambiguous in Task 2.
- Evidence can name valid but swapped endpoint IDs — test exact From/To binding in Task 3.
- A legacy ACTIVE row can continue affecting retrieval unless integration is fail-closed — test legacy text is excluded from v0.2 activation in Task 4.

---

## File Structure

- Modify `memory_gate_core/notion_memory_provider.py`: extract Notion URL property values.
- Create `memory_gate_core/evidence.py`: strict JSON parsing, schema validation, source identity and registered URL/DOI validation.
- Create `memory_gate_core/relation_validation.py`: explicit relation role matrix, endpoint binding, scope and temporal checks.
- Modify `memory_gate_core/retrieval.py`: require v0.2 validation before a Memory Graph edge can influence retrieval.
- Modify `tests/memory_gate/test_memory_gate_core_notion_provider.py`: URL extraction regression.
- Create `tests/memory_gate/test_memory_gate_evidence.py`: parser and source registry tests.
- Create `tests/memory_gate/test_memory_gate_relation_validation.py`: role/scope/endpoint tests.
- Modify `tests/memory_gate/test_memory_gate_core_retrieval.py`: legacy and v0.2 activation regression.
- Modify `docs/MEMORY_GATE_INTEGRITY_CONTRACT.md`: publish v0.2 behavior only after implementation tests pass.

## Interfaces

Task 2 produces:

- `EvidenceParseResult(structural_status: str, code: str | None, evidence: Mapping[str, Any] | None)`
- `SourceResolutionResult(provenance_status: str, code: str | None, source_record: Mapping[str, Any] | None)`
- `parse_evidence(value: object) -> EvidenceParseResult`
- `resolve_registered_source(evidence: Mapping[str, Any], source_records: Sequence[Mapping[str, Any]]) -> SourceResolutionResult`
- Structural status values: `VALID`, `LEGACY_UNVERIFIED`, `INVALID_EVIDENCE`.
- Provenance status values: `RESOLVED`, `SOURCE_MISSING`, `SOURCE_AMBIGUOUS`, `SOURCE_INVALID`, `SOURCE_VERSION_MISMATCH`.
- Relation status values: `VALID`, `INVALID_ROLE`, `INVALID_ENDPOINTS`, `INVALID_SCOPE`, `INVALID_VALIDITY`, `UNSUPPORTED_RELATION`.

Task 3 produces:

- `RelationValidationResult(status: str, code: str | None)`
- `validate_relation_evidence(relation_type: str, relation: Mapping[str, Any], evidence: Mapping[str, Any], source_record: Mapping[str, Any], from_record: Mapping[str, Any], to_record: Mapping[str, Any]) -> RelationValidationResult`
- Relation status values: `VALID`, `INVALID_ROLE`, `INVALID_ENDPOINTS`, `INVALID_SCOPE`, `INVALID_VALIDITY`, `UNSUPPORTED_RELATION`.

Task 4 consumes these interfaces from `_relation_warnings(records, relations)`. Source records are the provider records whose `source_name == "Memory Sources"`; graph endpoints continue to resolve only against `Memory Archive`.

---

### Task 1: Preserve Notion URL properties

**Files:**
- Modify: `memory_gate_core/notion_memory_provider.py:extract_page_properties`
- Test: `tests/memory_gate/test_memory_gate_core_notion_provider.py`

- [ ] **Step 1: Write failing tests**
  - Add `test_page_properties_extract_url_property`: a Notion property `{"type":"url","url":"https://example.org/source"}` is returned as the same string.
  - Add `test_page_properties_omit_empty_url_property`: a null URL is omitted, matching the existing empty-value policy.
  - Keep the existing email and phone exclusion assertions.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `pytest tests/memory_gate/test_memory_gate_core_notion_provider.py -k 'url_property' -q`

Expected: FAIL because URL is currently not extracted.

- [ ] **Step 3: Implement URL extraction**

Add a `kind == "url"` branch that preserves a string value and lets the existing empty-value guard omit null/empty values. Do not broaden other property handling.

- [ ] **Step 4: Run the focused tests and confirm GREEN**

Run: `pytest tests/memory_gate/test_memory_gate_core_notion_provider.py -k 'url_property' -q`

Expected: PASS.

- [ ] **Step 5: Commit**

`git add memory_gate_core/notion_memory_provider.py tests/memory_gate/test_memory_gate_core_notion_provider.py && git commit -m "fix: extract Notion source URLs"`

### Task 2: Parse strict Evidence v1 and resolve registered sources

**Files:**
- Create: `memory_gate_core/evidence.py`
- Create: `tests/memory_gate/test_memory_gate_evidence.py`

**Interfaces:**
- `parse_evidence(value: object) -> EvidenceValidationResult`
- `resolve_registered_source(evidence: Mapping[str, Any], source_records: Sequence[Mapping[str, Any]]) -> EvidenceValidationResult`

- [ ] **Step 1: Write failing parser tests**
  - `test_parse_valid_evidence_v1`: accepts the exact schema in the design doc.
  - `test_parse_rejects_malformed_json`
  - `test_parse_rejects_duplicate_json_keys`
  - `test_parse_rejects_unknown_or_missing_keys`
  - `test_parse_rejects_unknown_schema_version`
  - `test_parse_rejects_invalid_uuid_timestamp_digest_and_locator`
  - `test_parse_requires_scope_endpoint_ids_and_conditional_validity_shape`
  - `test_parse_rejects_missing_from_scope_id_or_to_scope_id`
  - `test_parse_rejects_oversized_evidence_payload_and_locator`

- [ ] **Step 2: Run parser tests and confirm RED**

Run: `pytest tests/memory_gate/test_memory_gate_evidence.py -q`

Expected: FAIL because `memory_gate_core.evidence` does not exist.

- [ ] **Step 3: Implement the typed result and strict parser**

Implement `EvidenceParseResult` and `parse_evidence`. Reject duplicate keys via `json.loads(..., object_pairs_hook=...)`; reject unknown keys; enforce the design doc's schema, UUID, timestamp, digest, locator allowlist, and bounded sizes. Return `LEGACY_UNVERIFIED` for ordinary non-JSON legacy text, `INVALID_EVIDENCE` for malformed JSON or malformed v1 structure, and `VALID` only for structurally valid v1 JSON. Do not coerce values.

- [ ] **Step 4: Run parser tests and confirm GREEN**

Run: `pytest tests/memory_gate/test_memory_gate_evidence.py -q`

Expected: parser tests PASS.

- [ ] **Step 5: Write failing registered-source tests**
  - `test_resolve_unique_registered_source_by_notion_page_id`
  - `test_resolve_rejects_missing_or_duplicate_source_id`
  - `test_resolve_blocks_empty_source_registry`
  - `test_resolve_accepts_registered_https_url_or_doi`
  - `test_resolve_rejects_http_credentials_unsafe_scheme_and_malformed_host`
  - `test_resolve_requires_exact_registered_version_match`
  - `test_resolve_allows_same_doi_for_distinct_registered_page_ids`

- [ ] **Step 6: Run source tests and confirm RED**

Run: `pytest tests/memory_gate/test_memory_gate_evidence.py -k 'source' -q`

Expected: FAIL because source resolution is not implemented.

- [ ] **Step 7: Implement registered-source resolution**

Resolve `source_ref` only against records with `source_name == "Memory Sources"` and exact matching Notion page UUID. Require exactly one match and at least one valid registered HTTPS URL or DOI. Require Evidence `source_version` to exactly equal `properties["Version"]`, with null matching an empty registry value. Duplicate page UUIDs in resolver input are ambiguous; identical DOI/URL values on distinct page UUIDs are allowed. Do not perform network I/O or claim the content digest was recalculated.

- [ ] **Step 8: Run all Evidence tests and confirm GREEN**

Run: `pytest tests/memory_gate/test_memory_gate_evidence.py -q`

Expected: PASS.

- [ ] **Step 9: Commit**

`git add memory_gate_core/evidence.py tests/memory_gate/test_memory_gate_evidence.py && git commit -m "feat: validate registered Evidence sources"`

### Task 3: Validate relation roles, endpoints, scope, and temporal ordering

**Files:**
- Create: `memory_gate_core/relation_validation.py`
- Create: `tests/memory_gate/test_memory_gate_relation_validation.py`

**Interface:**
- `validate_relation_evidence(relation_type: str, relation: Mapping[str, Any], evidence: Mapping[str, Any], source_record: Mapping[str, Any], from_record: Mapping[str, Any], to_record: Mapping[str, Any]) -> RelationValidationResult`

- [ ] **Step 1: Write failing tests**
  - `test_supports_requires_evidence_to_claim_roles`
  - `test_refutes_requires_counter_evidence_to_claim_roles`
  - `test_contradicts_requires_claim_to_claim_and_shared_scope`
  - `test_supersedes_requires_newer_to_older_and_ordered_validity`
  - `test_derived_from_requires_derived_to_source_roles`
  - `test_relation_endpoint_ids_must_match_evidence`
  - `test_scope_endpoint_ids_must_match_exact_relation_endpoints`
  - `test_scope_pair_consistency_by_relation_kind`
  - `test_derived_from_permits_distinct_endpoint_scopes`
  - `test_architecture_relation_types_are_not_memory_graph_types`

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `pytest tests/memory_gate/test_memory_gate_relation_validation.py -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the explicit role matrix**

Implement the exact relation-to-role mapping in the design doc. Require exact UUID equality between Evidence endpoint IDs and the relation's resolved From/To records. Require `scope.endpoint_ids` to equal the two canonical endpoint UUIDs in sorted order. SUPPORTS, REFUTES, CONTRADICTS, and SUPERSEDES require equal non-empty `from_scope_id` and `to_scope_id`; DERIVED_FROM requires both non-empty but permits them to differ. Require explicit ordered validity values for SUPERSEDES. Mark scope as curator-declared because the current archive schema has no Scope property. Unknown relation types fail closed.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run: `pytest tests/memory_gate/test_memory_gate_relation_validation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

`git add memory_gate_core/relation_validation.py tests/memory_gate/test_memory_gate_relation_validation.py && git commit -m "feat: validate Memory Graph relation roles"`

### Task 4: Enforce v0.2 validation at the retrieval activation boundary

**Files:**
- Modify: `memory_gate_core/retrieval.py:_relation_warnings`
- Modify: `tests/memory_gate/test_memory_gate_core_retrieval.py`

- [ ] **Step 1: Write failing integration tests**
  - `test_legacy_text_evidence_does_not_activate_relation_v02`: legacy Evidence is unchanged but cannot add support/refute/conflict/supersession/derivation effects.
  - `test_valid_v02_supports_relation_adds_support_warning`: valid registered source, exact endpoint IDs, roles, source version, and declared scope pair produce the existing support warning.
  - `test_unregistered_source_blocks_relation_activation`
  - `test_invalid_role_or_scope_blocks_relation_activation`
  - `test_invalid_evidence_does_not_create_supersession_suppression`
  - `test_derived_from_v02_cycle_still_fails_closed`

- [ ] **Step 2: Run integration tests and confirm RED**

Run: `pytest tests/memory_gate/test_memory_gate_core_retrieval.py -k 'evidence or relation' -q`

Expected: FAIL because retrieval still accepts any non-empty Evidence string.

- [ ] **Step 3: Integrate validation**

Pass all provider records into the existing relation validator. Index source pages separately from Memory Archive endpoints. Keep existing endpoint identity, relation status, stable relation UUID, direction, and cycle checks. A legacy or invalid Evidence result adds a precise warning and has no graph effect. Preserve separate structural, provenance/source-version, and role/scope validation statuses. Do not report the digest as verified unless artifact bytes were actually supplied and hashed. This means every currently plain-text Memory Relations Evidence row loses its ordinary retrieval effect until a curator replaces it with structured Evidence and registers the matching source; document and test this intentional rollout effect.

- [ ] **Step 4: Run integration tests and confirm GREEN**

Run: `pytest tests/memory_gate/test_memory_gate_core_retrieval.py -k 'evidence or relation' -q`

Expected: PASS.

- [ ] **Step 5: Run all Memory Gate tests**

Run: `pytest tests/memory_gate -q`

Expected: PASS with no regressions.

- [ ] **Step 6: Commit**

`git add memory_gate_core/retrieval.py tests/memory_gate/test_memory_gate_core_retrieval.py && git commit -m "feat: require validated Evidence for graph activation"`

### Task 5: Document v0.2 and verify repository-wide compatibility

**Files:**
- Modify: `docs/MEMORY_GATE_INTEGRITY_CONTRACT.md`
- Modify: `docs/superpowers/specs/2026-11-11-evidence-contract-v0-2-design.md` only if implementation reveals a necessary, documented correction.

- [ ] **Step 1: Update the contract**

Document the Evidence v1 envelope, registered source requirement, role matrix, fail-closed legacy behavior, and distinction between structural validation and truth. Preserve all v0.1 identity, graph separation, direction, and cycle guarantees.

- [ ] **Step 2: Run complete tests and static checks**

Run:
- `pytest -q`
- `python -m compileall -q authoritylab memory_gate_core`
- `flake8 authoritylab memory_gate_core tests`

Expected: PASS. If repository lint uses a narrower configured command, use the exact project workflow command and record it.

- [ ] **Step 3: Run supported CI**

Run the Python 3.11/3.12/3.13 matrix, Docker integration, and CodeQL workflows on the final implementation commit. Record exact commit SHA and run URLs. Do not reuse prior-commit results as final evidence.

- [ ] **Step 4: Independent self-review**

Review the full diff against the design doc and the Review Focus list. Verify no changes to Notion, `main`, PR #3's existing branch, or unrelated AuthorityLab files. No separate reviewer subagent is available in this tool session; report self-review as such rather than claiming independent review.

- [ ] **Step 5: Commit documentation**

`git add docs/MEMORY_GATE_INTEGRITY_CONTRACT.md && git commit -m "docs: specify Memory Gate Evidence contract v0.2"`

## Completion gate

Do not mark complete until:
- all TDD tasks are GREEN;
- full tests, compile, and lint are PASS;
- supported CI runs are PASS on the final SHA;
- final diff is reviewed;
- no existing Notion rows were mutated;
- no changes were made to `main` or merged.
