from __future__ import annotations

from agent.prompts.profiles import get_prompt_profile


LAYER1_SYSTEM_PROMPT = get_prompt_profile("default").layer1_system


def build_layer1_messages(paragraph: str, profile_id: str | None = None) -> list[dict[str, str]]:
    profile = get_prompt_profile(profile_id)
    return [
        {"role": "system", "content": profile.layer1_system},
        {"role": "user", "content": profile.layer1_user_template.format(paragraph=paragraph)},
    ]
