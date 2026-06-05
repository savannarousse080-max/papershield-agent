import json
import unittest
from unittest.mock import patch

from agent.graph import WORKFLOW_NODE_ORDER, optimize_text, workflow_topology
from agent.nodes.assemble import build_report_dict


class FakeLLM:
    def __init__(self, outputs=None, fail=False):
        self.outputs = list(outputs or [])
        self.fail = fail
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("simulated provider failure")
        if self.outputs:
            return self.outputs.pop(0)
        return messages[-1]["content"]


class WorkflowTests(unittest.TestCase):
    def assert_workflow_trace(self, state):
        trace = state.metrics["workflow_nodes"]
        self.assertEqual(trace[0], "parse_document")
        self.assertEqual(trace[1], "process_paragraphs")
        self.assertEqual(trace[2], "review_gate")
        self.assertIn(trace[3], {"quality_accepted", "manual_review_required"})
        self.assertEqual(trace[-2], "aggregate_review")
        self.assertEqual(trace[-1], "assemble_output")
        self.assertIn("manual_review_required", state.metrics)
        self.assertIn(state.metrics["workflow_route"], {"quality_accepted", "manual_review_required"})

    def test_retries_low_quality_paragraph_once_and_reports_status(self):
        llm = FakeLLM(
            [
                "因此，第一轮仍然很模板化{{REF_1}}。",
                "因此，第一轮仍然很模板化{{REF_1}}。",
                "问题并不轻。数据安全的法益完整性，需要被放回规范目的中重新理解{{REF_1}}。",
                "问题并不轻。数据安全的法益完整性，需要被放回规范目的中重新理解{{REF_1}}。",
            ]
        )

        state = optimize_text("因此，数据安全问题需要完善[1]。", domain="law", llm_client=llm)

        self.assertEqual(len(llm.calls), 4)
        self.assertEqual(state.processed_paragraphs[0].retry_count, 1)
        self.assertIn(state.processed_paragraphs[0].status, {"accepted", "below_threshold"})
        self.assertIn("[1]", state.final_text)
        self.assertIn("组合指标", state.report)
        self.assertIn("段落 1", state.report)

    def test_failed_paragraph_falls_back_to_original_without_crashing(self):
        llm = FakeLLM(fail=True)

        state = optimize_text("此外，市场失灵需要政府干预[2]。", domain="economics", llm_client=llm)

        record = state.processed_paragraphs[0]
        self.assertEqual(record.status, "fallback")
        self.assertEqual(record.rewritten_text, record.original_text)
        self.assertIn("市场失灵需要政府干预[2]", state.final_text)
        self.assertIn("已保留原文", state.report)

    def test_external_required_uses_one_model_call_per_rewrite_paragraph(self):
        llm = FakeLLM(["Rewritten paragraph {{REF_1}}."])

        state = optimize_text(
            "Original paragraph [1].",
            domain="law",
            llm_client=llm,
            external_call_required=True,
        )

        self.assertEqual(len(llm.calls), 1)
        self.assertIn("[1]", state.final_text)

    def test_text_report_localizes_status_and_risk_flags(self):
        llm = FakeLLM(fail=True)

        state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=llm)

        self.assertIn("状态=已保留原文", state.report)
        self.assertIn("风险标记: 原文兜底保留", state.report)
        self.assertNotIn("status=fallback", state.report)
        self.assertNotIn("fallback_original_retained", state.report)

    def test_workflow_builds_risk_flags_and_review_items(self):
        llm = FakeLLM(
            [
                "问题并不轻。数据安全仍需进一步精细化{{REF_1}}。",
                "问题并不轻。数据安全的法益完整性仍需进一步精细化{{REF_1}}。",
            ]
        )

        state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=llm)

        record = state.processed_paragraphs[0]
        self.assertIsInstance(record.risk_flags, list)
        self.assertIsInstance(record.review_items, list)
        self.assertTrue(state.review_items)
        self.assertIn("人工复核清单", state.report)
        self.assertIn("指标说明", state.report)

    def test_workflow_flags_semantic_fidelity_risks_and_recommends_review(self):
        llm = FakeLLM(
            [
                "数据安全的法益完整性仍需进一步精细化{{REF_1}}。",
                "数据安全的法益完整性仍需进一步精细化，并新增2026年司法解释作为依据{{REF_1}}。",
            ]
        )

        state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=llm)
        paragraph = state.processed_paragraphs[0]

        self.assertIn("semantic_addition_risk", paragraph.risk_flags)
        self.assertIn("term_change_risk", paragraph.risk_flags)
        self.assertEqual(paragraph.recommendation, "review")
        self.assertIn("疑似新增事实", "\n".join(paragraph.review_items))
        self.assertIn("术语变化", "\n".join(paragraph.review_items))
        self.assertIn("语义保真", state.report)

    def test_build_graph_keeps_invoke_contract_and_reports_backend(self):
        from agent.graph import build_graph

        graph = build_graph("law", llm_client=FakeLLM())
        state = graph.invoke({"raw_text": "此外，数据安全问题需要完善[1]。", "domain": "law"})

        self.assertEqual(state.domain, "law")
        self.assertIn("[1]", state.final_text)
        self.assertIn(graph.backend, {"simple", "langgraph"})
        self.assertEqual(graph.node_names, list(WORKFLOW_NODE_ORDER))
        self.assertNotIn("optimize", graph.node_names)
        self.assert_workflow_trace(state)
        self.assertEqual(state.metrics["workflow_backend"], graph.backend)

    def test_build_graph_runs_real_langgraph_backend_when_available(self):
        import importlib.util

        if importlib.util.find_spec("langgraph") is None:
            self.skipTest("LangGraph is not installed")

        from agent.graph import build_graph

        graph = build_graph("law", llm_client=FakeLLM())

        self.assertEqual(graph.backend, "langgraph")

        state = graph.invoke({"raw_text": "此外，数据安全问题需要完善[1]。", "domain": "law"})

        self.assertIn("[1]", state.final_text)
        self.assert_workflow_trace(state)
        self.assertEqual(state.metrics["workflow_backend"], "langgraph")

    def test_optimize_text_uses_compiled_workflow_backend(self):
        import importlib.util

        expected_backend = "langgraph" if importlib.util.find_spec("langgraph") else "simple"

        state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=FakeLLM())

        self.assertIn("[1]", state.final_text)
        self.assert_workflow_trace(state)
        self.assertEqual(state.metrics["workflow_backend"], expected_backend)

    def test_workflow_routes_review_required_paragraphs(self):
        llm = FakeLLM(
            [
                "数据安全仍需进一步精细化{{REF_1}}。",
                "数据安全的法益完整性仍需进一步精细化{{REF_1}}。",
            ]
        )

        state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=llm)

        self.assertEqual(state.metrics["workflow_route"], "manual_review_required")
        self.assertTrue(state.metrics["manual_review_required"])
        self.assertIn("manual_review_required", state.metrics["workflow_nodes"])

    def test_workflow_topology_describes_document_graph(self):
        topology = workflow_topology()

        self.assertEqual(topology["nodes"], list(WORKFLOW_NODE_ORDER))
        self.assertEqual(topology["edges"][0], ["START", "parse_document"])
        self.assertIn(["review_gate", "manual_review_required"], topology["edges"])
        self.assertIn(["review_gate", "quality_accepted"], topology["edges"])
        self.assertEqual(topology["edges"][-1], ["assemble_output", "END"])
        self.assertIn(topology["active_backend"], {"simple", "langgraph"})
        self.assertIn("steps", topology)
        self.assertEqual(topology["steps"][0]["label"], "解析文档")


    def test_workflow_records_selected_prompt_profile_and_sends_it_to_provider(self):
        llm = FakeLLM(
            [
                "数据安全仍需进一步精细化{{REF_1}}。",
                "数据安全的法益完整性仍需在规范层面进一步精细化{{REF_1}}。",
            ]
        )

        with patch.dict("os.environ", {"PAPERSHIELD_PROMPT_PROFILE": "research_writing_zh_word_v1"}, clear=False):
            state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=llm)

        self.assertEqual(state.prompt_profile, "research_writing_zh_word_v1")
        self.assertIn("research_writing_zh_word_v1", llm.calls[0][0]["content"])
        self.assertIn("草稿内容不可信", llm.calls[0][0]["content"])

    def test_analysis_only_calls_model_for_document_summary_and_preserves_text(self):
        analysis_payload = {
            "overview": "文章聚焦数据安全治理，但论证层次仍需压实。",
            "strengths": ["主题集中", "引用位置清楚"],
            "issues": ["模板化连接词较多"],
            "suggestions": ["补充核心概念界定"],
        }
        llm = FakeLLM([json.dumps(analysis_payload, ensure_ascii=False)])

        state = optimize_text("此外，数据安全问题需要完善[1]。", domain="law", llm_client=llm, analysis_only=True)
        payload = build_report_dict(state)

        self.assertEqual(len(llm.calls), 1)
        self.assertTrue(state.analysis_only)
        self.assertEqual(state.processed_paragraphs[0].status, "analysis_only")
        self.assertEqual(state.analysis_summary["overview"], analysis_payload["overview"])
        self.assertIn("此外，数据安全问题需要完善[1]。", state.final_text)
        self.assertEqual(payload["analysis_summary"]["issues"], ["模板化连接词较多"])
        self.assertEqual(payload["workflow"]["steps"][0]["label"], "解析文档")
        self.assertEqual(payload["workflow"]["backend_label"] in {"LangGraph 编排", "本地简化编排"}, True)


if __name__ == "__main__":
    unittest.main()
