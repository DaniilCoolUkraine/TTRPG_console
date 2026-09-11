"""All the actual Claude API calls live here — unchanged in design from
the local-script version, just adapted to run inside a Cloud Function
(lazy client init so import doesn't require the secret to be bound yet).
"""

import os
from pathlib import Path

from anthropic import Anthropic

import config
from state_manager import state_as_text

_client_instance = None


def _client() -> Anthropic:
    global _client_instance
    if _client_instance is None:
        _client_instance = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client_instance


RULES_PATH = Path(__file__).parent / "rules.md"


def load_rules_text() -> str:
    return RULES_PATH.read_text(encoding="utf-8")


def build_system_blocks(persona: str, state: dict) -> list:
    rules_and_persona = load_rules_text() + "\n\n---\n\nYour role:\n" + persona
    return [
        {
            "type": "text",
            "text": rules_and_persona,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                "Current campaign state (source of truth — never contradict "
                "it; if it's silent on something, you may improvise):\n"
                + state_as_text(state)
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def build_messages_for(pc_name: str, log: list, window: int) -> list:
    """Rebuild the recent scene log as an alternating user/assistant
    list from one PC's point of view."""
    recent = log[-window:]
    messages = []
    for entry in recent:
        speaker, text = entry["speaker"], entry["text"]
        role = "assistant" if speaker == pc_name else "user"
        line = text if role == "assistant" else f"{speaker}: {text}"
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"] += "\n" + line
        else:
            messages.append({"role": role, "content": line})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def get_pc_response(persona: str, model: str, state: dict, messages: list) -> str:
    if not messages:
        return "(waits, watching the scene.)"
    response = _client().messages.create(
        model=model,
        max_tokens=config.MAX_OUTPUT_TOKENS,
        system=build_system_blocks(persona, state),
        messages=messages,
    )
    return response.content[0].text


UPDATE_STATE_TOOL = {
    "name": "update_state",
    "description": (
        "Record any new facts, inventory changes, quest-flag changes, or "
        "NPC notes established in the recent messages. Only include things "
        "that actually happened — leave arrays or objects empty for "
        "categories where nothing changed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "new_facts": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Newly established world facts, promises, or clues.",
            },
            "inventory_changes": {
                "type": "object",
                "description": "Item name -> new owner/status, only for items that changed.",
            },
            "quest_flag_updates": {
                "type": "object",
                "description": "Flag name -> new value, only for flags that changed.",
            },
            "npc_notes": {
                "type": "object",
                "description": "NPC name -> short status/disposition note, only if changed.",
            },
        },
        "required": [
            "new_facts",
            "inventory_changes",
            "quest_flag_updates",
            "npc_notes",
        ],
    },
}

SCRIBE_SYSTEM_PROMPT = (
    "You are a meticulous scribe for a tabletop RPG session. Read the "
    "recent messages and call update_state with only what genuinely "
    "changed. Do not invent details, and do not restate facts that were "
    "already established earlier."
)


def run_scribe(state: dict, log: list, window: int) -> dict:
    recent = log[-window:]
    transcript_text = "\n".join(f"{e['speaker']}: {e['text']}" for e in recent)
    if not transcript_text:
        transcript_text = "(no messages yet)"

    response = _client().messages.create(
        model=config.SCRIBE_MODEL,
        max_tokens=500,
        tools=[UPDATE_STATE_TOOL],
        tool_choice={"type": "tool", "name": "update_state"},
        system=[{"type": "text", "text": SCRIBE_SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": transcript_text}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    return {
        "new_facts": [],
        "inventory_changes": {},
        "quest_flag_updates": {},
        "npc_notes": {},
    }
