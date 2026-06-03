from __future__ import annotations

from agent.prompts.profiles import COMMON_GUARDRAILS, get_prompt_profile


DOMAIN_CONFIGS = {
    "law": {
        "display_name": "法学（含数字刑法）",
        "scholar_role": "你是一位专注于数字刑法与知识产权的法学学者，熟悉教义学分析、法益保护、注意义务、规范目的和构成要件论证。",
        "protected_terms": ["法定构成要件", "法益", "注意义务", "教义学", "规范目的"],
        "few_shot_examples": [
            {
                "original": "这一行为对数据安全造成了影响，需要法律规制。",
                "rewritten": "该行为已经对数据安全的法益完整性构成实质性侵害，单纯的技术防护措施并不足以替代规范层面的义务确认。",
            },
            {
                "original": "不同国家的法律规定存在差异，给跨境数据流动带来挑战。",
                "rewritten": "从比较法视角看，各国立法在数据主权认定标准上的分歧，已经构成跨境数据流动中的规范冲突。",
            },
        ],
    },
    "economics": {
        "display_name": "经济学",
        "scholar_role": "你是一位研究制度经济学与产业政策的经济学学者，熟悉激励机制、路径依赖、制度性约束、边际效应和信息不对称。",
        "protected_terms": ["边际成本", "帕累托改进", "信息不对称", "路径依赖", "激励机制"],
        "few_shot_examples": [
            {
                "original": "市场失灵需要政府干预来解决。",
                "rewritten": "市场机制在信息不完全条件下的系统性失效，为政策性干预提供了规范意义上的正当性基础。",
            }
        ],
    },
    "general": {
        "display_name": "通用人文社科",
        "scholar_role": "你是一位人文社会科学领域的学术写作编辑，写作风格严谨、克制、具体，避免空洞套话。",
        "protected_terms": [],
        "few_shot_examples": [
            {
                "original": "这一现象在当今社会普遍存在，值得深入研究。",
                "rewritten": "这一现象的普遍性本身构成了值得追问的问题，也为理解当代社会结构性特征提供了入口。",
            }
        ],
    },
}


def get_domain_config(domain: str) -> dict:
    try:
        return DOMAIN_CONFIGS[domain]
    except KeyError as exc:
        supported = ", ".join(sorted(DOMAIN_CONFIGS))
        raise ValueError(f"Unknown domain: {domain}. Supported domains: {supported}") from exc


def build_layer2_messages(paragraph: str, domain: str, profile_id: str | None = None) -> list[dict[str, str]]:
    config = get_domain_config(domain)
    profile = get_prompt_profile(profile_id)
    examples = _format_examples(config["few_shot_examples"])
    system = profile.layer2_system_template.format(
        profile_id=profile.id,
        scholar_role=config["scholar_role"],
        common_guardrails=COMMON_GUARDRAILS,
        examples=examples,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": profile.layer2_user_template.format(paragraph=paragraph, domain=domain)},
    ]


def _format_examples(examples: list[dict[str, str]]) -> str:
    return "\n".join(
        f"原文示例：{example['original']}\n润色示例：{example['rewritten']}"
        for example in examples
    )
