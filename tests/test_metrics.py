import unittest

from scorer.metrics import evaluate_text_pair, sentence_length_variation, template_word_count
from scorer.perplexity import PerplexityScorer


class MetricsTests(unittest.TestCase):
    def test_template_words_and_sentence_variation_are_reported(self):
        original = "此外，数据治理需要完善。因此，制度建设需要推进。综上所述，这一问题值得研究[1]。"
        rewritten = "数据治理仍需被重新放回制度语境中讨论。问题并不轻。制度建设的推进，也要回应既有规范结构中的缺口[1]。"

        metrics = evaluate_text_pair(original, rewritten)

        self.assertGreater(template_word_count(original), template_word_count(rewritten))
        self.assertGreater(metrics.template_reduction, 0.79)
        self.assertGreater(sentence_length_variation(rewritten), sentence_length_variation(original))
        self.assertEqual(metrics.citation_retention, 1.0)
        self.assertGreater(metrics.rewritten_perplexity, 0)

    def test_citation_retention_detects_missing_references(self):
        metrics = evaluate_text_pair("已有研究表明这一点[1][2]。", "已有研究表明这一点[1]。")

        self.assertEqual(metrics.citation_retention, 0.5)

    def test_optional_perplexity_scorer_records_model_revision(self):
        scorer = PerplexityScorer(model_name=None, revision="safe-revision")

        self.assertEqual(scorer.revision, "safe-revision")


if __name__ == "__main__":
    unittest.main()
