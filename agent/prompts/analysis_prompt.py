from __future__ import annotations

from agent.prompts.layer2_prompts import get_domain_config
from agent.prompts.profiles import get_prompt_profile


def build_analysis_messages(text: str, domain: str, profile_id: str | None = None) -> list[dict[str, str]]:
    profile = get_prompt_profile(profile_id)
    domain_config = get_domain_config(domain)
    return [
        {"role": "system", "content": profile.analysis_system},
        {
            "role": "user",
            "content": profile.analysis_user_template.format(
                text=text,
                domain=domain_config["display_name"],
            ),
        },
    ]
