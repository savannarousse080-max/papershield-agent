from __future__ import annotations

from agent.llm import LLMClient
from agent.prompts.layer1_prompt import build_layer1_messages


def rewrite_syntax(paragraph: str, llm_client: LLMClient, prompt_profile: str | None = None) -> str:
    return llm_client.complete(build_layer1_messages(paragraph, prompt_profile)).strip()
