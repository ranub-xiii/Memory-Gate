import json
import unittest

from memory_gate_core.evidence_contract import (
    EVIDENCE_SCHEMA_V1,
    EvidenceContractError,
    validate_evidence_contract,
)

SOURCE_ID = "11111111-1111-4111-8111-111111111111"
SOURCE_REGISTRY = [{
    "id": SOURCE_ID,
    "source_name": "Memory Sources",
    "properties": {
        "Source": "Test source",
        "Source Type": "PRIMARY",
        "DOI": "10.1234/example",
        "URL": "https://example.org/source",
        "Version": "1",
    },
}]


def endpoint(title):
    return {
        "id": title,
        "source_name": "Memory Archive",
        "title": title,
        "properties": {
            "Type": "FACT",
            "Project": "Memory Gate",
            "Topic": "Evidence contract",
        },
    }


def evidence_payload(**overrides):
    value = {
        "schema": EVIDENCE_SCHEMA_V1,
        "relation": "SUPERSEDES",
        "from_role": "NEWER_CLAIM",
        "to_role": "OLDER_CLAIM",
        "scope": {
            "project": "Memory Gate",
            "topic": "Evidence contract",
            "statement": "The new claim supersedes the old claim in this scope.",
        },
        "sources": [SOURCE_ID],
    }
    value.update(overrides)
    return json.dumps(value, separators=(",", ":"))


class EvidenceContractTests(unittest.TestCase):
    def setUp(self):
        self.newer = endpoint("newer")
        self.older = endpoint("older")

    def validate(self, evidence, registry=None):
        return validate_evidence_contract(
            evidence, "SUPERSEDES", self.newer, self.older,
            SOURCE_REGISTRY if registry is None else registry,
        )

    def assert_code(self, code, evidence, registry=None):
        with self.assertRaises(EvidenceContractError) as raised:
            self.validate(evidence, registry)
        self.assertEqual(raised.exception.code, code)

    def test_valid_versioned_evidence_resolves_exact_registry_id(self):
        self.assertEqual(self.validate(evidence_payload()), (SOURCE_ID,))

    def test_legacy_free_text_is_rejected(self):
        self.assert_code("invalid_evidence_json", "A source mentioned in chat")

    def test_unknown_schema_version_is_rejected(self):
        self.assert_code(
            "unsupported_evidence_schema",
            evidence_payload(schema="memory-gate/evidence/v99"),
        )

    def test_duplicate_json_keys_are_rejected(self):
        text = (
            '{"schema":"memory-gate/evidence/v1","schema":"memory-gate/evidence/v1",'
            '"relation":"SUPERSEDES","from_role":"NEWER_CLAIM",'
            '"to_role":"OLDER_CLAIM","scope":{"project":"Memory Gate",'
            '"topic":"Evidence contract","statement":"A scoped claim."},'
            '"sources":["' + SOURCE_ID + '"]}'
        )
        self.assert_code("duplicate_json_key", text)

    def test_source_id_must_resolve_once_in_existing_registry(self):
        self.assert_code("evidence_source_missing", evidence_payload(), [])

    def test_duplicate_source_registry_identity_is_ambiguous(self):
        self.assert_code(
            "evidence_source_ambiguous",
            evidence_payload(),
            SOURCE_REGISTRY + SOURCE_REGISTRY,
        )

    def test_invalid_source_locator_is_rejected(self):
        invalid = [{
            "id": SOURCE_ID,
            "source_name": "Memory Sources",
            "properties": {
                "Source": "Test source",
                "Source Type": "PRIMARY",
                "URL": "javascript:alert(1)",
            },
        }]
        self.assert_code("evidence_source_invalid", evidence_payload(), invalid)

    def test_endpoint_role_type_mismatch_is_rejected(self):
        self.newer["properties"]["Type"] = "SOURCE"
        self.assert_code("endpoint_type_role_mismatch", evidence_payload())

    def test_project_scope_must_match_both_endpoints(self):
        self.older["properties"]["Project"] = "Other"
        self.assert_code("relation_project_scope_mismatch", evidence_payload())

    def test_topic_scope_must_match_both_supersedes_endpoints(self):
        self.older["properties"]["Topic"] = "Other topic"
        self.assert_code("relation_topic_scope_mismatch", evidence_payload())

    def test_duplicate_source_ids_are_rejected(self):
        self.assert_code(
            "duplicate_evidence_source_id",
            evidence_payload(sources=[SOURCE_ID, SOURCE_ID]),
        )

    def test_unknown_fields_are_rejected(self):
        value = json.loads(evidence_payload())
        value["truth"] = True
        self.assert_code("evidence_fields_mismatch", json.dumps(value))


if __name__ == "__main__":
    unittest.main()
