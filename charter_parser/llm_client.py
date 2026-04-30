"""Anthropic Claude client that turns cleaned PDF text into structured clauses.

We use tool-use as a structured-output mechanism: Claude is forced to call
``submit_clauses`` with a JSON-schema-validated payload, which removes the
entire class of "model returned almost-JSON" parsing bugs.

Prompt caching is enabled on the system prompt and tool definition, so a
re-run after a tweak to the input only pays the (small) write cost once and
hits the cache thereafter — useful while iterating on the page range or the
strikethrough heuristics.
"""

from __future__ import annotations

from typing import Any

from anthropic import Anthropic

from charter_parser.models import Clause, ClauseList


# Default to the latest Sonnet at module-load time; the CLI lets the caller
# override this. Sonnet handles a 30-page charter party in one shot and is
# substantially cheaper than Opus for what is essentially extraction work.
DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """\
You parse maritime charter party agreements (e.g. SHELLVOY 5, ASBATANKVOY).

You will receive cleaned text from Part II of such an agreement — the
numbered legal clauses. Your job is to segment that text into top-level
clauses and emit them via the `submit_clauses` tool.

Rules:
- A top-level clause begins with a number followed by a period and a
  space, at the start of a paragraph (e.g. "1.", "11.", "20A.").
- `id` is the clause number exactly as printed, without the trailing
  period (e.g. "1", "11", "20A").
- `title` is the heading printed alongside or above the clause (e.g.
  "Condition of vessel", "Cleanliness of tanks"). If the clause has no
  visible heading, use an empty string.
- `text` is the verbatim body of the clause. Include sub-clauses
  ("(a)", "(i)", "(1)", ...) inline, in order, joined by single spaces
  or newlines as in the source. Do NOT renumber, summarize, paraphrase
  or merge sub-clauses across clauses.
- The input has already had struck-through text removed. Treat what
  you see as the operative text; do not try to infer what was deleted.
- Strip page-break artifacts: "=== PAGE n ===" markers, page numbers,
  running headers ("Issued July 1987", "SHELLVOY 5"), and the vertical
  line numbers that appear at the right margin (1, 2, 3, ...).
- Preserve the order in which clauses appear. Do not deduplicate.
- Output only via the tool. Do not add explanatory prose.
"""

_SUBMIT_TOOL: dict[str, Any] = {
    "name": "submit_clauses",
    "description": "Submit the structured list of extracted top-level clauses.",
    "input_schema": {
        "type": "object",
        "properties": {
            "clauses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Clause number as printed (no trailing period).",
                        },
                        "title": {
                            "type": "string",
                            "description": "Heading text; empty string if absent.",
                        },
                        "text": {
                            "type": "string",
                            "description": "Verbatim body, sub-clauses included inline.",
                        },
                    },
                    "required": ["id", "title", "text"],
                },
            }
        },
        "required": ["clauses"],
    },
}

# Built once at import time; avoids a dict copy on every extract_clauses call.
_CACHED_TOOLS: list[dict[str, Any]] = [
    {**_SUBMIT_TOOL, "cache_control": {"type": "ephemeral"}}
]

_CACHED_SYSTEM = [
    {
        "type": "text",
        "text": _SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"},
    }
]


class ClauseExtractionError(RuntimeError):
    """Raised when the model does not return a usable tool call."""


def extract_clauses(
    text: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 32_000,
    api_key: str | None = None,
) -> list[Clause]:
    """Run Claude over ``text`` and return the parsed clauses.

    The Anthropic SDK reads ``ANTHROPIC_API_KEY`` from the environment by
    default; pass ``api_key`` explicitly if you keep it elsewhere.
    """
    client = Anthropic(api_key=api_key)  # SDK reads ANTHROPIC_API_KEY from env when None

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_CACHED_SYSTEM,
        tools=_CACHED_TOOLS,
        tool_choice={"type": "tool", "name": "submit_clauses"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Here is the cleaned Part II text of a charter party. "
                    "Extract every top-level numbered clause.\n\n"
                    f"<charter_party_text>\n{text}\n</charter_party_text>"
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_clauses":
            return ClauseList.model_validate(block.input).clauses

    raise ClauseExtractionError(
        f"Model {model} did not return a submit_clauses tool call "
        f"(stop_reason={response.stop_reason!r})."
    )
