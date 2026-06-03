import unittest

from agent.fidelity import analyze_fidelity, build_diff_segments


class FidelityTests(unittest.TestCase):
    def test_flags_suspicious_new_fact_and_term_change(self):
        result = analyze_fidelity(
            "此外，数据安全问题需要完善[1]。",
            "数据安全的法益完整性仍需进一步精细化，并新增2026年司法解释作为依据[1]。",
        )

        self.assertIn("semantic_addition_risk", result.risk_flags)
        self.assertIn("term_change_risk", result.risk_flags)
        self.assertGreaterEqual(result.added_terms_count, 1)
        self.assertGreaterEqual(result.term_change_count, 1)
        self.assertIn("疑似新增事实", result.review_items[0])

    def test_diff_segments_mark_equal_delete_and_insert_text(self):
        segments = build_diff_segments("数据安全需要完善。", "数据安全仍需进一步精细化。")
        operations = [segment["op"] for segment in segments]

        self.assertIn("equal", operations)
        self.assertIn("delete", operations)
        self.assertIn("insert", operations)
        self.assertTrue(all("text" in segment for segment in segments))


if __name__ == "__main__":
    unittest.main()
