import unittest

from agent.nodes.parse import parse_text
from utils.citation_handler import restore_citations


class ParseTextTests(unittest.TestCase):
    def test_protects_citations_and_skips_preserved_sections(self):
        sample = """一、问题提出

在数字经济时代，数据安全问题因此日益突出[1][2]。此外，相关法律规制亟待完善(张三, 2021)。脚注事实¹也需要保护。

图1 数据流动结构

参考文献
[1] 张三：《数据法研究》，2021。"""

        parsed = parse_text(sample)

        self.assertEqual(len(parsed.paragraphs), 1)
        paragraph = parsed.paragraphs[0].text
        self.assertIn("{{REF_1}}{{REF_2}}", paragraph)
        self.assertIn("{{REF_3}}", paragraph)
        self.assertIn("{{REF_4}}", paragraph)
        self.assertNotIn("参考文献", paragraph)
        self.assertEqual(len(parsed.citation_map), 4)

        restored = restore_citations(paragraph, parsed.citation_map)
        self.assertIn("[1][2]", restored)
        self.assertIn("(张三, 2021)", restored)
        self.assertIn("¹", restored)

    def test_preserves_document_order_with_titles_figures_and_references(self):
        sample = """第一章 绪论

这是需要处理的正文段落[3]。

表2 变量定义

References
Smith, 2020."""

        parsed = parse_text(sample)

        self.assertEqual([block.kind for block in parsed.blocks], ["heading", "paragraph", "table", "references"])
        self.assertEqual(parsed.blocks[1].paragraph_index, 0)
        self.assertIn("{{REF_1}}", parsed.blocks[1].text)
        self.assertEqual(parsed.blocks[-1].text, "References\nSmith, 2020.")

    def test_skips_front_matter_author_abstract_keywords_and_plain_headings(self):
        sample = """知识产权诉讼实务课程论文

郭晨

学院：法学院

学号：2026123456

摘要：本文围绕数据安全治理展开讨论。

关键词：数据安全；知识产权；平台治理

问题提出

此外，数据安全问题需要完善[1]。

参考文献
[1] 张三：《数据法研究》，2021。"""

        parsed = parse_text(sample)

        self.assertEqual(len(parsed.paragraphs), 1)
        self.assertEqual(
            [block.kind for block in parsed.blocks],
            ["heading", "metadata", "metadata", "metadata", "abstract", "keywords", "heading", "paragraph", "references"],
        )
        self.assertEqual(parsed.paragraphs[0].paragraph_index, 0)
        self.assertIn("{{REF_1}}", parsed.paragraphs[0].text)
        self.assertEqual(parsed.blocks[1].text, "郭晨")
        self.assertIn("参考文献", parsed.blocks[-1].text)


if __name__ == "__main__":
    unittest.main()
