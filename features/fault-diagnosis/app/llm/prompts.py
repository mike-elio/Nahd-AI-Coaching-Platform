from app.repositories.tags import AI_TAGS as _AI_TAGS
from app.repositories.tags import NETWORK_TAGS as _NETWORK_TAGS
from app.repositories.tags import SOFTWARE_TAGS as _SOFTWARE_TAGS


def build_prompt(user_problem: str) -> str:
    return f"""
You are a technical multi-label tag prediction assistant.

Analyze the user's technical problem and return:
- exactly one predicted domain from ai, sw, cn
- exactly 3 best tags
- a confidence score for each tag

STRICT RULES:
1. Choose tags ONLY from the allowed tags below.
2. Return exactly 3 tags.
3. Do NOT invent tags.
4. Tags may come from different allowed categories if that better matches the problem.
5. Prefer specific and troubleshooting-useful tags.
6. Avoid generic tags when a more specific one exists.
7. Order tags from highest confidence to lowest confidence.
8. Output ONLY valid JSON.
9. predicted_domain must be exactly one of: ai, sw, cn.

Allowed software tags:
{sorted(_SOFTWARE_TAGS)}

Allowed networking tags:
{sorted(_NETWORK_TAGS)}

Allowed AI tags:
{sorted(_AI_TAGS)}

Return ONLY this JSON:
{{
  "predicted_domain": "",
  "top_tags": [
    {{"tag": "", "confidence": 0.0}},
    {{"tag": "", "confidence": 0.0}},
    {{"tag": "", "confidence": 0.0}}
  ]
}}

User problem:
{user_problem}
""".strip()


__all__ = ["build_prompt"]
