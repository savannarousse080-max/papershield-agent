from __future__ import annotations


WORKFLOW_STEP_META = {
    "parse_document": {
        "label": "解析文档",
        "description": "识别正文、标题、作者信息、摘要、图表和参考文献。",
    },
    "process_paragraphs": {
        "label": "处理正文",
        "description": "仅将正文论述段落送入模型或本地诊断流程。",
    },
    "review_gate": {
        "label": "质量门禁",
        "description": "根据引用保留、模板化表达和语义保真风险判断审阅路线。",
    },
    "quality_accepted": {
        "label": "质量通过分支",
        "description": "当前结果未触发额外段落级复核要求。",
    },
    "manual_review_required": {
        "label": "人工复核分支",
        "description": "当前结果包含需要人工确认的风险或建议。",
    },
    "aggregate_review": {
        "label": "汇总建议",
        "description": "汇总逐段风险、指标和人工复核清单。",
    },
    "assemble_output": {
        "label": "生成输出",
        "description": "按原文档顺序合并最终稿和诊断报告。",
    },
}

BACKEND_LABELS = {
    "langgraph": "LangGraph 编排",
    "simple": "本地简化编排",
    "unknown": "未知编排",
}

ROUTE_LABELS = {
    "quality_accepted": "质量通过",
    "manual_review_required": "需要人工复核",
    "unknown": "未知路线",
}


def workflow_step_payload(node_ids: list[str] | tuple[str, ...]) -> list[dict[str, str]]:
    return [
        {
            "id": node_id,
            "label": WORKFLOW_STEP_META.get(node_id, {}).get("label", node_id),
            "description": WORKFLOW_STEP_META.get(node_id, {}).get("description", "工作流步骤。"),
            "status": "done",
        }
        for node_id in node_ids
    ]


def backend_label(backend: str | None) -> str:
    return BACKEND_LABELS.get(backend or "unknown", BACKEND_LABELS["unknown"])


def route_label(route: str | None) -> str:
    return ROUTE_LABELS.get(route or "unknown", ROUTE_LABELS["unknown"])


def manual_review_label(required: bool) -> str:
    return "已触发" if required else "未触发"
