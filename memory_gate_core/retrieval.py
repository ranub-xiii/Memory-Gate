"""Deterministic, provenance-aware ranking for scoped memory records.

This module intentionally uses lexical evidence only. It does not infer truth,
identity, or semantic equivalence from similarity.
"""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset({
    "a", "about", "after", "all", "also", "an", "and", "any", "are",
    "as", "at", "be", "been", "before", "but", "by", "can", "could",
    "do", "does", "for", "from", "get", "had", "has", "have", "how",
    "i", "if", "in", "into", "is", "it", "its", "me", "my", "of",
    "on", "or", "our", "please", "should", "so", "that", "the",
    "their", "them", "there", "this", "to", "up", "use", "was", "we",
    "what", "when", "where", "which", "who", "why", "will", "with",
    "would", "you", "your",
    "da", "i", "ili", "ali", "ako", "dok", "kako", "gdje", "gde",
    "kada", "zašto", "zasto", "što", "sto", "koji", "koja", "koje",
    "kojeg", "kojoj", "kojim", "čiji", "ciji", "je", "jesam", "jesi",
    "jesmo", "jeste", "jesu", "sam", "si", "smo", "ste", "su", "se",
    "u", "na", "iz", "od", "do", "za", "s", "sa", "bez", "po", "pri",
    "prema", "kao", "mi", "ti", "ja", "on", "ona", "ono", "oni", "one",
    "ovo", "ovaj", "ova", "taj", "ta", "te", "to", "bi", "bih", "bismo",
    "biste", "će", "ce", "može", "mozes", "mogu", "treba", "molim",
})
_INACTIVE = frozenset({"SUPERSEDED", "KILL", "CLOSED", "REFUTED"})
_CONFLICTING = frozenset({"CONTRADICTS", "REFUTES", "KILLS"})
_HISTORICAL_TERMS = frozenset({
    "history", "historical", "previous", "former", "superseded",
    "closed", "old", "past", "archive", "refuted", "rejected",
    "killed", "kill", "supersession", "legacy", "archived", "obsolete",
    "deprecated", "discarded", "abolished",
    # Croatian historical intent and common inflections.
    "povijest", "povijesni", "povijesna", "povijesno",
    "prethodni", "prethodna", "prethodno", "prethodne", "prethodnih",
    "prijašnji", "prijašnja", "prijašnje", "prijašnjih",
    "raniji", "ranija", "ranije", "ranijih",
    "stari", "stara", "staro", "stariji", "starija", "starije", "starijih",
    "prošli", "prošla", "prošlo", "prošle", "prošlih",
    "arhiva", "arhivski", "arhivsko",
    "opovrgnut", "opovrgnuta", "opovrgnuto", "opovrgnute",
    "pobijen", "pobijena", "pobijeno", "pobijene",
    "odbačen", "odbačena", "odbačeno", "odbačene",
    "odbijen", "odbijena", "odbijeno",
    "ukinut", "ukinuta", "ukinuto", "ugašen", "ugašena", "ugašeno",
    "zatvoren", "zatvorena", "zatvoreno",
    "nadjačan", "nadjačana", "nadjačano",
    "zamijenjen", "zamijenjena", "zamijenjeno",
    "poništen", "poništena", "poništeno",
    # Common unaccented variants.
    "prijasnji", "prijasnja", "prijasnje", "prosli", "prosla", "proslo",
    "odbacen", "odbacena", "odbaceno", "ugasen", "ugasena", "ugaseno",
    "ponisten", "ponistena", "ponisteno",
    # Closely related Serbian forms.
    "istorija", "istorijski", "istorijska",
})


def _tokens(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return [
        token for token in _TOKEN.findall(value.casefold())
        if len(token) > 1 and token not in _STOP
    ]


def _timestamp(value: object) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (ValueError, OverflowError):
        return None


# Notion page IDs are the only accepted identity keys. Titles, Memory IDs,
# and lexical similarity are display/retrieval metadata, never graph identity.
_PAGE_ID = re.compile(
    r"(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def _canonical_page_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not _PAGE_ID.fullmatch(candidate):
        return None
    try:
        return str(uuid.UUID(candidate))
    except ValueError:
        return None


def _memory_endpoint_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if candidate[:4].casefold() != "mem:":
        return None
    return _canonical_page_id(candidate[4:].strip())


def _cyclic_components(
    edges: Sequence[tuple[str, str]],
) -> tuple[dict[str, int], set[str]]:
    """Return SCC membership and nodes that participate in directed cycles."""
    adjacency: dict[str, list[str]] = {}
    reverse: dict[str, list[str]] = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
        adjacency.setdefault(target, [])
        reverse.setdefault(target, []).append(source)
        reverse.setdefault(source, [])

    visited: set[str] = set()
    finish_order: list[str] = []
    for start in adjacency:
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node, index = stack[-1]
            neighbors = adjacency[node]
            if index < len(neighbors):
                neighbor = neighbors[index]
                stack[-1] = (node, index + 1)
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append((neighbor, 0))
            else:
                finish_order.append(node)
                stack.pop()

    component_by_node: dict[str, int] = {}
    components: list[list[str]] = []
    for start in reversed(finish_order):
        if start in component_by_node:
            continue
        component_id = len(components)
        members: list[str] = []
        stack = [start]
        component_by_node[start] = component_id
        while stack:
            node = stack.pop()
            members.append(node)
            for neighbor in reverse[node]:
                if neighbor not in component_by_node:
                    component_by_node[neighbor] = component_id
                    stack.append(neighbor)
        components.append(members)

    cyclic_nodes: set[str] = set()
    for members in components:
        if len(members) > 1:
            cyclic_nodes.update(members)
        elif members and members[0] in adjacency[members[0]]:
            cyclic_nodes.add(members[0])
    return component_by_node, cyclic_nodes


def _relation_warnings(
    records: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, list[str]], set[int]]:
    warnings: dict[int, list[str]] = {}
    superseded: set[int] = set()
    # Memory Graph nodes are Memory Archive pages only. Architecture nodes
    # cannot be resolved by this Memory-only resolver.
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        if record.get("source_name") != "Memory Archive":
            continue
        page_id = _canonical_page_id(record.get("id"))
        if page_id is not None:
            indexed.setdefault(page_id, []).append(record)

    dag_edges: dict[
        str,
        list[tuple[str, str, Mapping[str, Any], Mapping[str, Any], str]],
    ] = {"SUPERSEDES": [], "DERIVED_FROM": []}

    def add_warning(record: Mapping[str, Any], warning: str) -> None:
        warnings.setdefault(id(record), []).append(warning)

    for relation in relations:
        props = relation.get("properties")
        props = props if isinstance(props, Mapping) else {}
        relation_type = str(props.get("Relation Type", "")).upper()
        if relation_type not in {
            "SUPPORTS", "REFUTES", "CONTRADICTS",
            "SUPERSEDES", "DERIVED_FROM",
        }:
            # PART_OF/TESTS/USES are not interpreted as Memory Graph edges.
            continue

        status = str(props.get("Status", "")).upper()
        if status in {"REJECTED", "SUPERSEDED"}:
            continue

        source_id = _memory_endpoint_id(props.get("From Memory"))
        target_id = _memory_endpoint_id(props.get("To Memory"))
        source_matches = indexed.get(source_id, []) if source_id else []
        target_matches = indexed.get(target_id, []) if target_id else []
        candidates = {
            id(record): record for record in source_matches + target_matches
        }
        relation_id = _canonical_page_id(relation.get("id"))
        edge = (
            f"{relation_type}:"
            f"{props.get('From Memory')}->{props.get('To Memory')}"
            f"[edge_id={relation_id or 'missing'}]"
        )

        invalid_sides = []
        if source_id is None:
            invalid_sides.append("from_identity")
        if target_id is None:
            invalid_sides.append("to_identity")
        if invalid_sides:
            for record in candidates.values():
                add_warning(
                    record,
                    f"unresolved_relation_endpoint:{edge}:"
                    + ",".join(invalid_sides),
                )
            continue

        if len(source_matches) > 1 or len(target_matches) > 1:
            for record in candidates.values():
                add_warning(record, f"ambiguous_relation_endpoint:{edge}")
            continue

        if not source_matches or not target_matches:
            missing = "from" if not source_matches else "to"
            for record in candidates.values():
                add_warning(
                    record, f"unresolved_relation_endpoint:{edge}:{missing}"
                )
            continue

        source_record = source_matches[0]
        target_record = target_matches[0]

        if status == "UNRESOLVED":
            for record in (source_record, target_record):
                add_warning(record, f"unresolved_relation:{edge}")
            continue

        if status != "ACTIVE":
            for record in (source_record, target_record):
                add_warning(
                    record,
                    f"blocked_relation_status:{edge}:{status or 'MISSING'}",
                )
            continue

        # Evidence is provenance metadata, not proof of truth.
        if relation_id is None:
            for record in (source_record, target_record):
                add_warning(record, f"blocked_relation_provenance:{edge}")
            continue
        evidence = props.get("Evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            for record in (source_record, target_record):
                add_warning(
                    record, f"blocked_relation_missing_evidence:{edge}"
                )
            continue

        if relation_type in {"SUPERSEDES", "DERIVED_FROM"}:
            dag_edges[relation_type].append((
                source_id, target_id, source_record, target_record, edge
            ))
        elif relation_type == "SUPPORTS":
            add_warning(target_record, f"supported_by_relation:{edge}")
        elif relation_type == "REFUTES":
            add_warning(source_record, f"refutes_claim_relation:{edge}")
            add_warning(target_record, f"refuted_by_relation:{edge}")
        elif relation_type == "CONTRADICTS":
            # Symmetric warning; neither claim is selected as the winner.
            for record in (source_record, target_record):
                add_warning(record, f"conflicting_relation:{edge}")

    # SUPERSEDES and DERIVED_FROM are separate directed acyclic relations.
    cycle_nodes_by_type: dict[str, set[str]] = {}
    for relation_type, edges in dag_edges.items():
        components, cycle_nodes = _cyclic_components([
            (source_id, target_id)
            for source_id, target_id, *_ in edges
        ])
        cycle_nodes_by_type[relation_type] = cycle_nodes
        for source_id, target_id, source_record, target_record, edge in edges:
            is_cycle_edge = (
                source_id in cycle_nodes
                and target_id in cycle_nodes
                and components.get(source_id) == components.get(target_id)
            )
            if is_cycle_edge:
                warning = f"cycle_relation:{relation_type}:{edge}"
                add_warning(source_record, warning)
                add_warning(target_record, warning)
            elif source_id in cycle_nodes or target_id in cycle_nodes:
                warning = f"cycle_blocked_relation:{relation_type}:{edge}"
                add_warning(source_record, warning)
                add_warning(target_record, warning)

    # A SUPERSEDES edge touching any cycle participant cannot suppress.
    for source_id, target_id, source_record, target_record, edge in dag_edges[
        "SUPERSEDES"
    ]:
        if (
            source_id in cycle_nodes_by_type["SUPERSEDES"]
            or target_id in cycle_nodes_by_type["SUPERSEDES"]
        ):
            continue
        superseded.add(id(target_record))
        add_warning(target_record, f"superseded_by_relation:{edge}")

    # DERIVED_FROM is explanatory provenance; neither end is suppressed.
    for source_id, target_id, source_record, target_record, edge in dag_edges[
        "DERIVED_FROM"
    ]:
        if (
            source_id in cycle_nodes_by_type["DERIVED_FROM"]
            or target_id in cycle_nodes_by_type["DERIVED_FROM"]
        ):
            continue
        add_warning(source_record, f"derived_from_relation:{edge}")
        add_warning(target_record, f"source_of_derivation_relation:{edge}")

    return warnings, superseded

def rank_memory_records(
    records: Sequence[Mapping[str, Any]],
    query: str | None,
    *,
    now: float,
    limit: int = 24,
    relations: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Rank memory records; suppress inactive/future/superseded facts fail-closed.

    Ranking is deterministic BM25-like lexical overlap with field weights and a
    small recency tie-breaker. Status is metadata, never a truth guarantee.
    """
    if type(now) not in (int, float) or not math.isfinite(now):
        raise ValueError("now must be a finite timestamp")
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be positive")
    query_terms = list(dict.fromkeys(_tokens(query or "")))
    query_set = set(query_terms)
    historical = bool(query_set & _HISTORICAL_TERMS)
    relation_warnings, relation_superseded = _relation_warnings(records, relations)

    prepared: list[dict[str, Any]] = []
    document_frequency: dict[str, int] = {}
    for record in records:
        props = record.get("properties")
        props = props if isinstance(props, Mapping) else {}
        status = str(props.get("Status", "")).upper()
        record_type = str(props.get("Type", "")).upper()
        title = str(record.get("title", ""))
        superseded_by = props.get("Superseded By")
        cycle_participant = any(
            warning.startswith("cycle_relation:SUPERSEDES:")
            for warning in relation_warnings.get(id(record), [])
        )
        if not historical and (
            (
                status in _INACTIVE
                and not (status == "SUPERSEDED" and cycle_participant)
            )
            or record_type in {"KILL", "CLOSED"}
            or (bool(superseded_by) and not cycle_participant)
            or (
                id(record) in relation_superseded
                and not cycle_participant
            )
        ):
            continue
        created = _timestamp(props.get("Created At"))
        updated = _timestamp(props.get("Updated At"))
        if any(
            stamp is not None and stamp > float(now) + 300
            for stamp in (created, updated)
        ):
            continue
        fields = {
            "title": title,
            "topic": props.get("Topic", ""),
            "project": props.get("Project", ""),
            "tags": props.get("Tags", ""),
            "content": props.get("Content", ""),
            "notes": props.get("Notes", ""),
            "details": " ".join(str(props.get(key, "")) for key in (
                "Purpose", "Current State", "Latest Changes",
                "Open Questions", "Key Sources", "Evidence Level",
                "Source", "Type",
            )),
            "body": record.get("body", ""),
        }
        tokens = {name: _tokens(value) for name, value in fields.items()}
        all_terms = set(token for values in tokens.values() for token in values)
        for term in all_terms:
            document_frequency[term] = document_frequency.get(term, 0) + 1
        prepared.append({
            "record": record, "props": props, "tokens": tokens,
            "created": created, "updated": updated, "status": status,
            "warnings": relation_warnings.get(id(record), []),
        })

    count = max(1, len(prepared))
    weights = {
        "title": 7.0, "topic": 5.0, "project": 4.0,
        "tags": 3.0, "content": 2.5, "notes": 1.8,
        "details": 1.2, "body": 1.0,
    }
    ranked: list[dict[str, Any]] = []
    for item in prepared:
        score = 0.0
        if query_terms:
            for field, values in item["tokens"].items():
                frequencies: dict[str, int] = {}
                for token in values:
                    frequencies[token] = frequencies.get(token, 0) + 1
                for term in query_terms:
                    tf = frequencies.get(term, 0)
                    if not tf:
                        continue
                    df = document_frequency.get(term, 0)
                    inverse = math.log(1.0 + (count - df + 0.5) / (df + 0.5))
                    score += weights[field] * inverse * (1.0 + math.log(tf))
            title_norm = " ".join(item["tokens"]["title"])
            query_norm = " ".join(query_terms)
            if query_norm and query_norm in title_norm:
                score += 8.0
            if score <= 0:
                continue
        stamp = item["updated"] or item["created"]
        if stamp is not None:
            age_days = max(0.0, (float(now) - stamp) / 86400.0)
            score += max(0.0, 0.35 * (1.0 - age_days / 365.0))
        if item["status"] in {"VERIFIED", "EXACT", "PASS", "SUPPORTED"}:
            score += 0.15
        source_name = str(item["record"].get("source_name", ""))
        if source_name == "Memory Archive" and item["status"] in {
            "CONTRADICTED", "UNKNOWN", "PENDING", "UNVERIFIED"
        }:
            item["warnings"].append(f"evidence_status:{item['status']}")
        record_type = str(item["props"].get("Type", "")).upper()
        if record_type in {"ASSUMPTION", "HYPOTHESIS", "UNKNOWN", "OPEN_QUESTION"}:
            item["warnings"].append(f"record_type:{record_type}")
        ranked.append({
            **item["record"],
            "retrieval_score": round(score, 6),
            "retrieval_warnings": list(dict.fromkeys(item["warnings"])),
            "record_status": item["status"] or "UNSPECIFIED",
        })

    if not query_terms:
        ranked.sort(key=lambda item: (
            _timestamp((item.get("properties") or {}).get("Updated At")) or
            _timestamp((item.get("properties") or {}).get("Created At")) or 0.0,
            str(item.get("title", "")).casefold(),
        ), reverse=True)
    else:
        ranked.sort(key=lambda item: (
            item["retrieval_score"], str(item.get("title", "")).casefold()
        ), reverse=True)
    return ranked[:limit]
