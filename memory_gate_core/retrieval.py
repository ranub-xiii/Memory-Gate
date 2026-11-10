"""Deterministic, provenance-aware ranking for scoped memory records.

This module intentionally uses lexical evidence only. It does not infer truth,
identity, or semantic equivalence from similarity.
"""
from __future__ import annotations

import math
import re
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
})
_INACTIVE = frozenset({"SUPERSEDED", "KILL", "CLOSED", "REFUTED"})
_CONFLICTING = frozenset({"CONTRADICTS", "REFUTES", "KILLS"})
_HISTORICAL_TERMS = frozenset({
    "history", "historical", "previous", "former", "superseded",
    "closed", "old", "past", "archive",
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


def _norm(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(_TOKEN.findall(value.casefold()))


def _record_keys(record: Mapping[str, Any]) -> set[str]:
    props = record.get("properties")
    props = props if isinstance(props, Mapping) else {}
    values = [record.get("id"), record.get("title"), props.get("Memory ID")]
    return {key for value in values if (key := _norm(str(value)))}


def _relation_warnings(
    records: Sequence[Mapping[str, Any]],
    relations: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, list[str]], set[str]]:
    warnings: dict[int, list[str]] = {}
    superseded: set[str] = set()
    indexed = [(record, _record_keys(record)) for record in records]
    for relation in relations:
        props = relation.get("properties")
        props = props if isinstance(props, Mapping) else {}
        relation_type = str(props.get("Relation Type", "")).upper()
        status = str(props.get("Status", "")).upper()
        source = _norm(props.get("From Memory", ""))
        target = _norm(props.get("To Memory", ""))
        if not source or not target or status not in {"ACTIVE", "UNRESOLVED"}:
            continue
        if relation_type == "SUPERSEDES":
            superseded.add(target)
        if relation_type not in _CONFLICTING:
            continue
        for record, keys in indexed:
            if source in keys or target in keys:
                warnings.setdefault(id(record), []).append(
                    f"conflicting_relation:{relation_type}:{props.get('From Memory')}->{props.get('To Memory')}"
                )
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
        keys = _record_keys(record)
        if not historical and (
            status in _INACTIVE or record_type in {"KILL", "CLOSED"}
            or bool(superseded_by) or bool(keys & relation_superseded)
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
