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
        self.assertEqual(ranked[0]["title"], "Memory Gate retrieval")
        self.assertGreater(ranked[0]["retrieval_score"], ranked[1]["retrieval_score"])

    def test_superseded_closed_kill_and_future_records_are_not_active(self):
        records = [
            self.record("Current decision", Status="VERIFIED"),
            self.record("Old decision", Status="SUPERSEDED"),
            self.record("Closed task", Status="CLOSED"),
            self.record("Killed hypothesis", Status="KILL"),
            self.record(
                "Future record", Status="VERIFIED",
                **{"Created At": "2030-01-01T00:00:00Z"},
            ),
        ]
        ranked = rank_memory_records(
            records, None, now=self.NOW, limit=10,
        )
        self.assertEqual([item["title"] for item in ranked], ["Current decision"])

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
            "unresolved_relation:CONTRADICTS" in item["retrieval_warnings"][0]
            for item in ranked
        ))

    def test_contradicted_and_unknown_records_are_not_silently_promoted(self):
        records = [
            self.record("Unresolved memory", Status="CONTRADICTED"),
            self.record("Unknown memory", Status="UNKNOWN"),
        ]
        ranked = rank_memory_records(records, None, now=self.NOW)
        self.assertEqual(
            {item["evidence_status"] for item in ranked},
            {"CONTRADICTED", "UNKNOWN"},
        )
        self.assertTrue(all(item["retrieval_warnings"] for item in ranked))

    def test_query_with_no_overlap_returns_no_false_match(self):
        records = [self.record("Memory Gate", Topic="Retrieval")]
        ranked = rank_memory_records(
            records, "quantum chromodynamics", now=self.NOW,
        )
        self.assertEqual(ranked, [])

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
