"""Chain-of-thought support for prompt-based reasoning.

The model is asked (via the agent's system prompt) to wrap its step-by-step
reasoning in <think>…</think> tags before the final answer. `split_reasoning`
separates that reasoning from the answer so the UI can show the thinking above
the response and keep it out of the stored transcript (thinking is ephemeral).

This is prompt-based CoT — it works with any instruction-following model behind
the provider, including OpenAI-family models served through the Reidchat proxy,
which have no native Anthropic "thinking" content blocks.
"""
from __future__ import annotations

import re

# Appended to the agent's system prompt to elicit the reasoning block.
COT_SYSTEM_SUFFIX = (
    "\n\nAlways begin your reply with concise, first-person step-by-step reasoning "
    "enclosed in <think> and </think> tags. Put nothing but that reasoning between "
    "the tags. After the closing </think> tag, write your final answer for the user."
)

# Matches <think>…</think> or <thinking>…</thinking>, case-insensitively, across lines.
_THINK_RE = re.compile(r"<think(?:ing)?>(.*?)</think(?:ing)?>", re.DOTALL | re.IGNORECASE)


def split_reasoning(text: str) -> tuple[str | None, str]:
    """Split model output into (reasoning, answer).

    Returns (None, text) when there is no well-formed reasoning block, so a model
    that ignores the format never has its answer hidden. Whitespace is trimmed.
    """
    if not text:
        return None, text
    match = _THINK_RE.search(text)
    if match is None:
        return None, text.strip()
    thinking = match.group(1).strip()
    answer = (text[: match.start()] + text[match.end():]).strip()
    return (thinking or None), answer
