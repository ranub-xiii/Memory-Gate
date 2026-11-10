import unittest

from memory_gate_core.retrieval import rank_memory_records


class MemoryRetrievalTests(unittest.TestCase):
    NOW = 1_800_000_000.0

    def record(self, title, **properties):
        return {
            "id": title.lower().replace(" ", "-"),
            "title": title,
            "source_name": "Memory Archive",
            "properties": properties,
            "body": "",
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
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Old project policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
            }
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
        relation = {
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Old policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
            }
        }
        ranked = rank_memory_records(
            [old, new], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual([item["title"] for item in ranked], ["New policy"])

    def test_unresolved_supersedes_relation_warns_without_suppressing(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = {
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Old policy",
                "Relation Type": "SUPERSEDES",
                "Status": "UNRESOLVED",
            }
        }
        ranked = rank_memory_records(
            [old, new], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual(
            {item["title"] for item in ranked},
            {"Old policy", "New policy"},
        )
        by_title = {item["title"]: item for item in ranked}
        self.assertTrue(all(
            any(warning.startswith("unresolved_relation:SUPERSEDES:")
                for warning in item["retrieval_warnings"])
            for item in by_title.values()
        ))

    def test_ambiguous_supersedes_endpoint_warns_without_suppressing(self):
        old_one = {
            **self.record("Old policy", Status="VERIFIED"),
            "id": "old-policy-one",
        }
        old_two = {
            **self.record("Old policy", Status="VERIFIED"),
            "id": "old-policy-two",
        }
        new = self.record("New policy", Status="VERIFIED")
        relation = {
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Old policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
            }
        }
        ranked = rank_memory_records(
            [old_one, old_two, new], None, now=self.NOW,
            relations=[relation], limit=5,
        )
        self.assertEqual(len(ranked), 3)
        for record in (old_one, old_two, new):
            result = next(item for item in ranked if item["id"] == record["id"])
            self.assertTrue(any(
                warning.startswith("ambiguous_relation_endpoint:SUPERSEDES:")
                for warning in result["retrieval_warnings"]
            ))

    def test_historical_retrieval_labels_active_supersession(self):
        old = self.record("Old policy", Status="VERIFIED")
        new = self.record("New policy", Status="VERIFIED")
        relation = {
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Old policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
            }
        }
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
        relation = {
            "properties": {
                "From Memory": "New policy",
                "To Memory": "Missing policy",
                "Relation Type": "SUPERSEDES",
                "Status": "ACTIVE",
            }
        }
        ranked = rank_memory_records(
            [source], None, now=self.NOW, relations=[relation],
        )
        self.assertEqual(len(ranked), 1)
        self.assertTrue(any(
            warning.startswith("unresolved_relation_endpoint:SUPERSEDES:")
            for warning in ranked[0]["retrieval_warnings"]
        ))

    def test_contradiction_relation_is_explicitly_labelled(self):
        first = self.record("Claim A", Status="VERIFIED")
        second = self.record("Claim B", Status="SUPPORTED")
        relation = {
            "properties": {
                "From Memory": "Claim A",
                "To Memory": "Claim B",
                "Relation Type": "CONTRADICTS",
                "Status": "UNRESOLVED",
            }
        }
        ranked = rank_memory_records(
            [first, second], None, now=self.NOW,
            relations=[relation],
        )
        self.assertTrue(all(item["retrieval_warnings"] for item in ranked))
        self.assertTrue(all(
            "conflicting_relation:CONTRADICTS" in item["retrieval_warnings"][0]
            for item in ranked
        ))

    def test_relation_matching_does_not_collapse_distinct_short_suffixes(self):
        first = self.record("Claim A", Status="VERIFIED")
        second = self.record("Claim B", Status="SUPPORTED")
        third = self.record("Claim C", Status="VERIFIED")
        relation = {
            "properties": {
                "From Memory": "Claim A",
                "To Memory": "Claim B",
                "Relation Type": "CONTRADICTS",
                "Status": "ACTIVE",
            }
        }
        ranked = rank_memory_records(
            [first, second, third], None, now=self.NOW,
            relations=[relation],
        )
        by_title = {item["title"]: item for item in ranked}
        self.assertTrue(by_title["Claim A"]["retrieval_warnings"])
        self.assertTrue(by_title["Claim B"]["retrieval_warnings"])
        self.assertEqual(by_title["Claim C"]["retrieval_warnings"], [])

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
