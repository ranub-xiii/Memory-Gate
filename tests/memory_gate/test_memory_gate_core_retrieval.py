import unittest
import uuid

from memory_gate_core.retrieval import rank_memory_records


class MemoryRetrievalTests(unittest.TestCase):
    NOW = 1_800_000_000.0

    def record(self, title, **properties):
        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"memory:{title}")),
            "title": title,
            "source_name": "Memory Archive",
            "properties": properties,
            "body": "",
        }

    def relation(self, source, target, relation_type, *, status="ACTIVE",
                 evidence="reviewed evidence reference"):
        key = f"{relation_type}:{source['id']}:{target['id']}:{status}"
        return {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"relation:{key}")),
            "properties": {
                "From Memory": f"mem:{source['id']}",
                "To Memory": f"mem:{target['id']}",
                "Relation Type": relation_type,
                "Status": status,
                "Evidence": evidence,
            },
        }

    def test_relevant_topic_and_project_rank_above_unrelated_record(self):
        records = [
            self.record(
                "Memory Gate retrieval",
                Topic="Memory ranking and retrieval",
                Project="Memory Gate",
                Notes="Relevance ranking and temporal memory",
                Status="VERIFIED",
                **{"Updated At": "2026-11-09T00:00:00Z"},
            ),
            self.record(
                "Ski equipment",
                Topic="Ski shopping",
                Project="Personal",
                Notes="Bindings and ski length",
                Status="VERIFIED",
                **{"Updated At": "2026-11-09T00:00:00Z"},
            ),
        ]
        ranked = rank_memory_records(
            records, "continue Memory Gate retrieval ranking",
            now=self.NOW, limit=2,
        )
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["title"], "Memory Gate retrieval")

    def test_superseded_closed_kill_and_future_records_are_not_active(self):
        records = [
            self.record("Current decision", Status="VERIFIED"),
            self.record("Old decision", Status="SUPERSEDED"),
            self.record("Closed task", Status="CLOSED"),
            self.record("Killed hypothesis", Status="KILL"),
            self.record("Killed type", Type="KILL"),
            self.record(
                "Future record", Status="VERIFIED",
                **{"Created At": "2030-01-01T00:00:00Z"},
            ),
        ]
        ranked = rank_memory_records(
            records, None, now=self.NOW, limit=10,
        )
        self.assertEqual([item["title"] for item in ranked], ["Current decision"])

    def test_relation_endpoints_are_scoped_to_memory_archive_records(self):
        archive_new = self.record("New policy", Status="VERIFIED")
        project_old = {
            **self.record("Old project policy", Status="VERIFIED"),
            "id": "project-old-policy",
            "source_name": "Memory Projects",
        }
        relation = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "relation:cross-source")),
            "properties": {
                "From Memory": f"mem:{archive_new['id']}",
                "To Memory": "Old project policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
                "Evidence": "reviewed evidence reference",
            },
        }
        ranked = rank_memory_records(
            [archive_new, project_old], None, now=self.NOW,
            relations=[relation], limit=5,
        )
        ranked_by_id = {item["id"]: item for item in ranked}
        self.assertIn(archive_new["id"], ranked_by_id)
        self.assertIn(project_old["id"], ranked_by_id)
        self.assertTrue(any(
            warning.startswith(
                "unresolved_relation_endpoint:SUPERSEDES:"
            )
            for warning in ranked_by_id[archive_new["id"]]["retrieval_warnings"]
        ))

    def test_explicit_supersedes_relation_suppresses_target(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES")
        ranked = rank_memory_records(
            [old, new], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual([item["title"] for item in ranked], ["New policy"])

    def test_unresolved_supersedes_has_no_ordinary_retrieval_effect(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES", status="UNRESOLVED")
        ranked = rank_memory_records(
            [old, new], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual(
            {item["title"] for item in ranked},
            {"Old policy", "New policy"},
        )
        self.assertTrue(all(
            item["retrieval_warnings"] == [] for item in ranked
        ))

    def test_ambiguous_supersedes_endpoint_warns_without_suppressing(self):
        duplicate_page_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, "memory:duplicate-old-policy")
        )
        old_one = {
            **self.record("Old policy one", Status="VERIFIED"),
            "id": duplicate_page_id,
        }
        old_two = {
            **self.record("Old policy two", Status="VERIFIED"),
            "id": duplicate_page_id,
        }
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old_one, "SUPERSEDES")
        ranked = rank_memory_records(
            [old_one, old_two, new], None, now=self.NOW,
            relations=[relation], limit=5,
        )
        self.assertEqual(len(ranked), 3)
        duplicate_results = [
            item for item in ranked if item["id"] == duplicate_page_id
        ]
        self.assertEqual(len(duplicate_results), 2)
        self.assertTrue(all(any(
            warning.startswith("ambiguous_relation_endpoint:SUPERSEDES:")
            for warning in item["retrieval_warnings"]
        ) for item in duplicate_results))
        new_result = next(item for item in ranked if item["id"] == new["id"])
        self.assertTrue(any(
            warning.startswith("ambiguous_relation_endpoint:SUPERSEDES:")
            for warning in new_result["retrieval_warnings"]
        ))

    def test_historical_retrieval_labels_active_supersession(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES")
        ranked = rank_memory_records(
            [old, new], "historical old policy", now=self.NOW,
            relations=[relation], limit=5,
        )
        old_result = next(item for item in ranked if item["title"] == "Old policy")
        self.assertTrue(any(
            warning.startswith("superseded_by_relation:SUPERSEDES:")
            for warning in old_result["retrieval_warnings"]
        ))

    def test_missing_supersedes_endpoint_is_visible_on_resolved_record(self):
        source = self.record("New policy", Status="VERIFIED")
        missing = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "memory:missing-policy")),
            "title": "Missing policy",
            "source_name": "Memory Archive",
            "properties": {},
            "body": "",
        }
        relation = self.relation(source, missing, "SUPERSEDES")
        ranked = rank_memory_records(
            [source], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual(len(ranked), 1)
        self.assertTrue(any(
            warning.startswith("unresolved_relation_endpoint:SUPERSEDES:")
            for warning in ranked[0]["retrieval_warnings"]
        ))

    def test_unresolved_contradiction_has_no_ordinary_retrieval_effect(self):
        first = self.record("Claim A", Status="VERIFIED")
        second = self.record("Claim B", Status="SUPPORTED")
        relation = self.relation(
            first, second, "CONTRADICTS", status="UNRESOLVED",
        )
        ranked = rank_memory_records(
            [first, second], None, now=self.NOW,
            relations=[relation],
        )
        self.assertTrue(all(
            item["retrieval_warnings"] == [] for item in ranked
        ))

    def test_relation_matching_does_not_collapse_distinct_short_suffixes(self):
        first = self.record("Claim A", Status="VERIFIED")
        second = self.record("Claim B", Status="SUPPORTED")
        third = self.record("Claim C", Status="VERIFIED")
        relation = self.relation(first, second, "CONTRADICTS")
        ranked = rank_memory_records(
            [first, second, third], None, now=self.NOW,
            relations=[relation],
        )
        by_title = {item["title"]: item for item in ranked}
        self.assertTrue(by_title["Claim A"]["retrieval_warnings"])
        self.assertTrue(by_title["Claim B"]["retrieval_warnings"])
        self.assertEqual(by_title["Claim C"]["retrieval_warnings"], [])

    def test_native_notion_relation_id_arrays_resolve_single_endpoints(self):
        old = self.record("Old native relation target", Status="VERIFIED")
        new = self.record("New native relation source", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES")
        relation["properties"]["From Memory"] = [new["id"]]
        relation["properties"]["To Memory"] = [old["id"]]
        ranked = rank_memory_records(
            [old, new], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual([item["id"] for item in ranked], [new["id"]])

    def test_native_notion_relation_with_multiple_ids_is_ambiguous(self):
        first = self.record("Ambiguous source one", Status="VERIFIED")
        second = self.record("Ambiguous source two", Status="VERIFIED")
        old = self.record("Target must remain visible", Status="VERIFIED")
        relation = self.relation(first, old, "SUPERSEDES")
        relation["properties"]["From Memory"] = [first["id"], second["id"]]
        ranked = rank_memory_records(
            [first, second, old], None, now=self.NOW, relations=[relation],
        )
        by_id = {item["id"]: item for item in ranked}
        self.assertEqual(set(by_id), {first["id"], second["id"], old["id"]})
        self.assertTrue(all(any(
            warning.startswith("ambiguous_relation_endpoint:SUPERSEDES:")
            for warning in item["retrieval_warnings"]
        ) for item in ranked))

    def test_empty_native_notion_relation_is_blocked(self):
        old = self.record("Target with empty source relation", Status="VERIFIED")
        new = self.record("Source with empty relation property", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES")
        relation["properties"]["From Memory"] = []
        ranked = rank_memory_records(
            [old, new], None, now=self.NOW, relations=[relation],
        )
        by_id = {item["id"]: item for item in ranked}
        self.assertEqual(set(by_id), {old["id"], new["id"]})
        self.assertTrue(any(
            "unresolved_relation_endpoint:SUPERSEDES:" in warning
            and "from_missing_identity" in warning
            for warning in by_id[old["id"]]["retrieval_warnings"]
        ))
        # The source page cannot be identified from an empty endpoint list;
        # attaching the warning to it would invent an identity association.
        self.assertEqual(by_id[new["id"]]["retrieval_warnings"], [])

    def test_title_text_is_not_accepted_as_endpoint_identity(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "relation:title-only")),
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Old policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
                "Evidence": "reviewed evidence reference",
            },
        }
        ranked = rank_memory_records([old, new], None, now=self.NOW, relations=[relation])
        self.assertEqual({item["id"] for item in ranked}, {old["id"], new["id"]})
        self.assertFalse(any(
            warning.startswith("superseded_by_relation:")
            for item in ranked for warning in item["retrieval_warnings"]
        ))

    def test_same_title_with_different_page_ids_remains_two_nodes(self):
        old_one = self.record("Old policy", Status="VERIFIED")
        old_two = {
            **self.record("Old policy", Status="VERIFIED"),
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "memory:second-old-policy")),
        }
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old_one, "SUPERSEDES")
        ranked = rank_memory_records([old_one, old_two, new], None, now=self.NOW, relations=[relation])
        ids = {item["id"] for item in ranked}
        self.assertIn(old_two["id"], ids)
        self.assertIn(new["id"], ids)
        self.assertNotIn(old_one["id"], ids)

    def test_title_change_does_not_change_resolved_identity(self):
        old = self.record("Original title", Status="VERIFIED")
        new = self.record("New title", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES")
        old["title"] = "Renamed later"
        ranked = rank_memory_records([old, new], None, now=self.NOW, relations=[relation])
        self.assertNotIn(old["id"], {item["id"] for item in ranked})

    def test_active_contradiction_is_distinct_from_unresolved_candidate(self):
        first = self.record("Claim A", Status="VERIFIED")
        second = self.record("Claim B", Status="SUPPORTED")
        relation = self.relation(first, second, "CONTRADICTS", status="ACTIVE")
        ranked = rank_memory_records([first, second], None, now=self.NOW, relations=[relation])
        self.assertTrue(all(any(
            warning.startswith("conflicting_relation:CONTRADICTS:")
            for warning in item["retrieval_warnings"]
        ) for item in ranked))

    def test_supersedes_cycle_keeps_superseded_nodes_visible(self):
        first = self.record("Policy A", Status="SUPERSEDED")
        second = self.record("Policy B", Status="SUPERSEDED")
        relations = [
            self.relation(first, second, "SUPERSEDES"),
            self.relation(second, first, "SUPERSEDES"),
        ]
        ranked = rank_memory_records([first, second], None, now=self.NOW, relations=relations)
        self.assertEqual({item["id"] for item in ranked}, {first["id"], second["id"]})
        self.assertTrue(all(any(
            warning.startswith("cycle_relation:SUPERSEDES:")
            for warning in item["retrieval_warnings"]
        ) for item in ranked))

    def test_derived_from_cycle_is_reported_without_suppressing_records(self):
        derived = self.record("Derived A", Status="VERIFIED")
        source = self.record("Source B", Status="VERIFIED")
        relations = [
            self.relation(derived, source, "DERIVED_FROM"),
            self.relation(source, derived, "DERIVED_FROM"),
        ]
        ranked = rank_memory_records([derived, source], None, now=self.NOW, relations=relations)
        self.assertEqual({item["id"] for item in ranked}, {derived["id"], source["id"]})
        self.assertTrue(all(any(
            warning.startswith("cycle_relation:DERIVED_FROM:")
            for warning in item["retrieval_warnings"]
        ) for item in ranked))

    def test_cycle_does_not_disable_separate_acyclic_supersession(self):
        first = self.record("Cycle A", Status="VERIFIED")
        second = self.record("Cycle B", Status="VERIFIED")
        current = self.record("Current C", Status="VERIFIED")
        old = self.record("Old D", Status="VERIFIED")
        relations = [
            self.relation(first, second, "SUPERSEDES"),
            self.relation(second, first, "SUPERSEDES"),
            self.relation(current, old, "SUPERSEDES"),
        ]
        ranked = rank_memory_records(
            [first, second, current, old], None, now=self.NOW, relations=relations,
        )
        ranked_ids = {item["id"] for item in ranked}
        self.assertIn(first["id"], ranked_ids)
        self.assertIn(second["id"], ranked_ids)
        self.assertIn(current["id"], ranked_ids)
        self.assertNotIn(old["id"], ranked_ids)

    def test_active_relation_without_evidence_is_blocked(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES", evidence="")
        ranked = rank_memory_records([old, new], None, now=self.NOW, relations=[relation])
        self.assertEqual({item["id"] for item in ranked}, {old["id"], new["id"]})
        self.assertTrue(all(any(
            warning.startswith("blocked_relation_missing_evidence:")
            for warning in item["retrieval_warnings"]
        ) for item in ranked))

    def test_active_relation_without_relation_page_id_is_blocked(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = self.relation(new, old, "SUPERSEDES")
        relation.pop("id")
        ranked = rank_memory_records([old, new], None, now=self.NOW, relations=[relation])
        self.assertEqual({item["id"] for item in ranked}, {old["id"], new["id"]})
        self.assertTrue(all(any(
            warning.startswith("blocked_relation_provenance:")
            for warning in item["retrieval_warnings"]
        ) for item in ranked))

    def test_architecture_identity_is_not_resolved_in_memory_graph(self):
        memory = self.record("Memory node", Status="VERIFIED")
        architecture = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "arch:component")),
            "title": "Component node",
            "source_name": "Architecture Graph",
            "properties": {"Status": "VERIFIED"},
            "body": "",
        }
        relation = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "relation:cross-graph")),
            "properties": {
                "From Memory": f"mem:{memory['id']}",
                "To Memory": f"arch:{architecture['id']}",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
                "Evidence": "reviewed evidence reference",
            },
        }
        ranked = rank_memory_records([memory, architecture], None, now=self.NOW, relations=[relation])
        self.assertEqual({item["id"] for item in ranked}, {memory["id"], architecture["id"]})

    def test_absent_relation_is_not_interpreted_as_negative_relation(self):
        first = self.record("Claim A", Status="VERIFIED")
        second = self.record("Claim B", Status="VERIFIED")
        ranked = rank_memory_records([first, second], None, now=self.NOW)
        self.assertTrue(all(item["retrieval_warnings"] == [] for item in ranked))


    def test_self_supersedes_cycle_keeps_superseded_record_visible(self):
        record = self.record(
            "Self-superseding policy",
            Status="SUPERSEDED",
            **{"Superseded By": "Self-superseding policy"},
        )
        relation = self.relation(record, record, "SUPERSEDES")
        ranked = rank_memory_records(
            [record], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual([item["id"] for item in ranked], [record["id"]])
        self.assertTrue(any(
            warning.startswith("cycle_relation:SUPERSEDES:")
            for warning in ranked[0]["retrieval_warnings"]
        ))
        self.assertFalse(any(
            warning.startswith("superseded_by_relation:")
            for warning in ranked[0]["retrieval_warnings"]
        ))

    def test_derived_from_self_cycle_is_reported_without_removal(self):
        record = self.record("Self-derived result", Status="VERIFIED")
        relation = self.relation(record, record, "DERIVED_FROM")
        ranked = rank_memory_records(
            [record], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual([item["id"] for item in ranked], [record["id"]])
        self.assertTrue(any(
            warning.startswith("cycle_relation:DERIVED_FROM:")
            for warning in ranked[0]["retrieval_warnings"]
        ))

    def test_edges_touching_cycle_participants_cannot_suppress_other_nodes(self):
        first = self.record("Cycle A", Status="VERIFIED")
        second = self.record("Cycle B", Status="VERIFIED")
        incoming = self.record("Incoming C", Status="VERIFIED")
        outgoing = self.record("Outgoing D", Status="VERIFIED")
        relations = [
            self.relation(first, second, "SUPERSEDES"),
            self.relation(second, first, "SUPERSEDES"),
            self.relation(incoming, first, "SUPERSEDES"),
            self.relation(first, outgoing, "SUPERSEDES"),
        ]
        ranked = rank_memory_records(
            [first, second, incoming, outgoing], None,
            now=self.NOW, relations=relations,
        )
        by_id = {item["id"]: item for item in ranked}
        self.assertEqual(
            set(by_id), {first["id"], second["id"], incoming["id"], outgoing["id"]}
        )
        for record in (first, second):
            self.assertTrue(any(
                warning.startswith("cycle_relation:SUPERSEDES:")
                for warning in by_id[record["id"]]["retrieval_warnings"]
            ))
        for record in (first, incoming, outgoing):
            self.assertTrue(any(
                warning.startswith("cycle_blocked_relation:SUPERSEDES:")
                for warning in by_id[record["id"]]["retrieval_warnings"]
            ))
        self.assertFalse(any(
            warning.startswith("superseded_by_relation:")
            for item in ranked for warning in item["retrieval_warnings"]
        ))

    def test_unclassified_relation_types_have_no_memory_graph_effect(self):
        first = self.record("Legacy source", Status="VERIFIED")
        second = self.record("Legacy target", Status="VERIFIED")
        unclassified = (
            "DEPENDS_ON", "RELATED_TO", "CONFIRMS", "KILLS",
            "OPENS", "CITES", "SAME_ENTITY", "POSSIBLE_MATCH",
            "PART_OF", "TESTS", "USES",
        )
        for relation_type in unclassified:
            with self.subTest(relation_type=relation_type):
                relation = self.relation(first, second, relation_type)
                ranked = rank_memory_records(
                    [first, second], None, now=self.NOW,
                    relations=[relation],
                )
                self.assertEqual(
                    {item["id"] for item in ranked},
                    {first["id"], second["id"]},
                )
                self.assertTrue(all(
                    item["retrieval_warnings"] == [] for item in ranked
                ))

    def test_contradicted_and_unknown_records_are_not_silently_promoted(self):
        records = [
            self.record("Unresolved memory", Status="CONTRADICTED"),
            self.record("Unknown memory", Status="UNKNOWN"),
        ]
        ranked = rank_memory_records(records, None, now=self.NOW)
        self.assertEqual(
            {item["record_status"] for item in ranked},
            {"CONTRADICTED", "UNKNOWN"},
        )
        self.assertTrue(all(item["retrieval_warnings"] for item in ranked))

    def test_page_body_terms_contribute_to_ranking(self):
        records = [
            self.record("General note", Status="VERIFIED"),
            {
                **self.record("Unrelated title", Status="VERIFIED"),
                "body": "Trnje worker recovery and persistent task state",
            },
        ]
        ranked = rank_memory_records(
            records, "worker recovery", now=self.NOW, limit=2,
        )
        self.assertEqual(ranked[0]["title"], "Unrelated title")

    def test_query_with_no_overlap_returns_no_false_match(self):
        records = [self.record("Memory Gate", Topic="Retrieval")]
        ranked = rank_memory_records(
            records, "quantum chromodynamics", now=self.NOW,
        )
        self.assertEqual(ranked, [])

    def test_refuted_records_are_retrievable_only_in_historical_context(self):
        records = [
            self.record("Refuted model", Status="REFUTED"),
            self.record("Current model", Status="VERIFIED"),
        ]
        normal = rank_memory_records(
            records, "model", now=self.NOW, limit=5,
        )
        historical = rank_memory_records(
            records, "why refuted model", now=self.NOW, limit=5,
        )
        self.assertNotIn("Refuted model", [item["title"] for item in normal])
        self.assertIn("Refuted model", [item["title"] for item in historical])

    def test_croatian_historical_intent_retrieves_refuted_records(self):
        records = [
            self.record("Refuted model", Status="REFUTED"),
            self.record("Current model", Status="VERIFIED"),
        ]
        for historical_term in (
            "povijest", "prethodno", "opovrgnuto", "arhiva",
        ):
            with self.subTest(historical_term=historical_term):
                ranked = rank_memory_records(
                    records, f"zašto je {historical_term} model",
                    now=self.NOW, limit=5,
                )
                self.assertIn(
                    "Refuted model", [item["title"] for item in ranked]
                )

    def test_historical_query_still_rejects_future_dated_records(self):
        records = [
            self.record("Old policy", Status="SUPERSEDED"),
            self.record(
                "Future policy", Status="VERIFIED",
                **{"Created At": "2030-01-01T00:00:00Z"},
            ),
        ]
        ranked = rank_memory_records(
            records, "historical policy", now=self.NOW, limit=5,
        )
        self.assertEqual([item["title"] for item in ranked], ["Old policy"])

    def test_assumption_and_hypothesis_types_are_labelled(self):
        records = [
            self.record("Assumed model", Type="ASSUMPTION"),
            self.record("Possible model", Type="HYPOTHESIS"),
        ]
        ranked = rank_memory_records(records, None, now=self.NOW)
        self.assertTrue(all(item["retrieval_warnings"] for item in ranked))

    def test_historical_query_can_retrieve_superseded_record(self):
        records = [
            self.record("Old policy", Status="SUPERSEDED"),
            self.record("Current policy", Status="VERIFIED"),
        ]
        ranked = rank_memory_records(
            records, "historical old policy", now=self.NOW, limit=5,
        )
        self.assertIn("Old policy", [item["title"] for item in ranked])


if __name__ == "__main__":
    unittest.main()
