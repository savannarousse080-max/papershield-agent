from __future__ import annotations

from agent.llm import LLMClient
from agent.prompts.layer2_prompts import build_layer2_messages


def rewrite_lexical(paragraph: str, domain: str, llm_client: LLMClient, prompt_profile: str | None = None) -> str:
    return llm_client.complete(build_layer2_messages(paragraph, domain, prompt_profile)).strip()
