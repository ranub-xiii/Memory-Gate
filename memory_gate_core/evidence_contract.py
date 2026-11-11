"""Strict, versioned provenance contract for Memory Graph relations."""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

EVIDENCE_SCHEMA_V1 = "memory-gate/evidence/v1"
_MAX_EVIDENCE_BYTES = 16_384
_MAX_SOURCE_REFS = 8
_ALLOWED_KEYS = frozenset({
    "schema", "relation", "from_role", "to_role", "scope", "sources",
})
_SOURCE_TYPES = frozenset({
    "PRIMARY", "SECONDARY", "REFERENCE", "DATASET", "USER_PROVIDED",
    "CALCULATION",
})
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")

_RELATION_ROLES = {
    "SUPPORTS": ("EVIDENCE", "CLAIM"),
    "REFUTES": ("COUNTER_EVIDENCE", "CLAIM"),
    "CONTRADICTS": ("CLAIM", "CLAIM"),
    "SUPERSEDES": ("NEWER_CLAIM", "OLDER_CLAIM"),
    "DERIVED_FROM": ("DERIVED_RECORD", "SOURCE_RECORD"),
}
_CLAIM_TYPES = frozenset({
    "FACT", "DEFINITION", "USER_DECISION", "USER_PREFERENCE",
    "HYPOTHESIS", "MODEL", "DECISION", "OPEN_QUESTION",
})
_EVIDENCE_TYPES = frozenset({
    "SOURCE", "OBSERVATION", "RESULT", "ARTIFACT", "DERIVATION", "FACT",
})
_ROLE_TYPES = {
    "EVIDENCE": _EVIDENCE_TYPES,
    "COUNTER_EVIDENCE": _EVIDENCE_TYPES,
    "CLAIM": _CLAIM_TYPES,
    "NEWER_CLAIM": _CLAIM_TYPES,
    "OLDER_CLAIM": _CLAIM_TYPES,
    "DERIVED_RECORD": frozenset({
        "DERIVATION", "RESULT", "MODEL", "FACT", "DEFINITION",
        "DECISION", "USER_DECISION",
    }),
    "SOURCE_RECORD": frozenset({
        "SOURCE", "OBSERVATION", "RESULT", "ARTIFACT", "FACT",
        "DEFINITION", "USER_DECISION", "USER_PREFERENCE", "MODEL",
    }),
}


class EvidenceContractError(ValueError):
    """Raised when a relation's provenance contract is invalid."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceContractError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise EvidenceContractError("non_finite_json_number")


def _canonical_uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        canonical = str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None
    return canonical if value == canonical else None


def _required_text(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= maximum
        and value == value.strip()
    )


def _source_is_valid(record: Mapping[str, Any]) -> bool:
    if record.get("source_name") != "Memory Sources":
        return False
    properties = record.get("properties")
    if not isinstance(properties, Mapping):
        return False
    if not _required_text(properties.get("Source"), maximum=512):
        return False
    source_type = str(properties.get("Source Type", "")).upper()
    if source_type not in _SOURCE_TYPES:
        return False

    doi = properties.get("DOI")
    has_doi = (
        isinstance(doi, str)
        and doi == doi.strip()
        and bool(_DOI.fullmatch(doi))
    )
    url = properties.get("URL")
    has_url = False
    if isinstance(url, str) and url and url == url.strip():
        try:
            parsed = urlsplit(url)
            port = parsed.port
            has_url = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and (port is None or 1 <= port <= 65535)
            )
        except ValueError:
            has_url = False
    has_local_provenance = (
        source_type in {"USER_PROVIDED", "CALCULATION"}
        and _required_text(properties.get("Notes"), maximum=4096)
    )
    return has_doi or has_url or has_local_provenance


def validate_evidence_contract(
    evidence: object,
    relation_type: str,
    source_record: Mapping[str, Any],
    target_record: Mapping[str, Any],
    source_registry: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Validate Evidence v1 and return canonical Memory Sources page IDs.

    Legacy free text is deliberately rejected. Registry identity is exact
    Notion page UUID matching; titles, DOIs, and URLs are never identity keys.
    This validates provenance structure, not source quality or claim truth.
    """
    if not isinstance(evidence, str) or not evidence.strip():
        raise EvidenceContractError("missing_evidence")
    try:
        encoded = evidence.encode("utf-8")
    except UnicodeError:
        raise EvidenceContractError("invalid_evidence_encoding") from None
    if len(encoded) > _MAX_EVIDENCE_BYTES:
        raise EvidenceContractError("evidence_too_large")

    try:
        payload = json.loads(
            evidence,
            object_pairs_hook=_unique_object_pairs,
            parse_constant=_reject_constant,
        )
    except EvidenceContractError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        raise EvidenceContractError("invalid_evidence_json") from None

    if not isinstance(payload, dict) or set(payload) != _ALLOWED_KEYS:
        raise EvidenceContractError("evidence_fields_mismatch")
    if payload.get("schema") != EVIDENCE_SCHEMA_V1:
        raise EvidenceContractError("unsupported_evidence_schema")

    relation_type = relation_type.upper()
    roles = _RELATION_ROLES.get(relation_type)
    if roles is None or payload.get("relation") != relation_type:
        raise EvidenceContractError("evidence_relation_mismatch")
    if payload.get("from_role") != roles[0] or payload.get("to_role") != roles[1]:
        raise EvidenceContractError("evidence_role_mismatch")

    scope = payload.get("scope")
    if not isinstance(scope, dict) or set(scope) != {
        "project", "topic", "statement",
    }:
        raise EvidenceContractError("invalid_evidence_scope")
    if not (
        _required_text(scope.get("project"), maximum=256)
        and _required_text(scope.get("topic"), maximum=256)
        and _required_text(scope.get("statement"), maximum=2048)
    ):
        raise EvidenceContractError("invalid_evidence_scope")

    source_ids = payload.get("sources")
    if not isinstance(source_ids, list) or not 1 <= len(source_ids) <= _MAX_SOURCE_REFS:
        raise EvidenceContractError("invalid_evidence_sources")
    canonical_ids = [_canonical_uuid(item) for item in source_ids]
    if any(item is None for item in canonical_ids):
        raise EvidenceContractError("invalid_evidence_source_id")
    if len(set(canonical_ids)) != len(canonical_ids):
        raise EvidenceContractError("duplicate_evidence_source_id")

    registry_index: dict[str, list[Mapping[str, Any]]] = {}
    for item in source_registry:
        if not isinstance(item, Mapping):
            continue
        page_id = _canonical_uuid(item.get("id"))
        if page_id is not None:
            registry_index.setdefault(page_id, []).append(item)
    for page_id in canonical_ids:
        matches = registry_index.get(page_id, [])
        if len(matches) != 1:
            raise EvidenceContractError(
                "evidence_source_missing" if not matches
                else "evidence_source_ambiguous"
            )
        if not _source_is_valid(matches[0]):
            raise EvidenceContractError("evidence_source_invalid")

    source_properties = source_record.get("properties")
    target_properties = target_record.get("properties")
    if not isinstance(source_properties, Mapping) or not isinstance(target_properties, Mapping):
        raise EvidenceContractError("missing_endpoint_properties")
    source_type = str(source_properties.get("Type", "")).upper()
    target_type = str(target_properties.get("Type", "")).upper()
    if (
        source_type not in _ROLE_TYPES[roles[0]]
        or target_type not in _ROLE_TYPES[roles[1]]
    ):
        raise EvidenceContractError("endpoint_type_role_mismatch")

    project = scope["project"]
    source_project = source_properties.get("Project")
    target_project = target_properties.get("Project")
    if not (
        isinstance(source_project, str)
        and isinstance(target_project, str)
        and source_project == project
        and target_project == project
    ):
        raise EvidenceContractError("relation_project_scope_mismatch")

    topic = scope["topic"]
    source_topic = source_properties.get("Topic")
    target_topic = target_properties.get("Topic")
    if relation_type in {"SUPPORTS", "REFUTES"}:
        topic_matches = target_topic == topic
    elif relation_type in {"CONTRADICTS", "SUPERSEDES"}:
        topic_matches = source_topic == topic and target_topic == topic
    else:  # DERIVED_FROM: scope names the derived record's topic.
        topic_matches = source_topic == topic
    if not topic_matches:
        raise EvidenceContractError("relation_topic_scope_mismatch")

    return tuple(canonical_ids)  # type: ignore[arg-type]
