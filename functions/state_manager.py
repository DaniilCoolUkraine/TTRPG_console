"""Structured long-term memory for the campaign — the whole reason this
system doesn't lose track of facts the way a raw growing transcript
would. Backed by Firestore now instead of a local file, so every
device reading/writing through the same Cloud Functions sees the same
state.
"""

import json

from firebase_admin import firestore

DEFAULT_STATE = {
    "party": {},
    "inventory": {},
    "quest_flags": {},
    "established_facts": [],
    "npc_notes": {},
}

CAMPAIGN_PATH = ("campaigns", "default")
MAX_LOG_ENTRIES = 200  # trim old scene-log entries; state itself is unbounded


def _doc_ref():
    return firestore.client().collection(CAMPAIGN_PATH[0]).document(CAMPAIGN_PATH[1])


def load_campaign() -> dict:
    """Returns {"state": ..., "log": [...], "turns_since_update": int}."""
    snap = _doc_ref().get()
    if not snap.exists:
        initial = {
            "state": json.loads(json.dumps(DEFAULT_STATE)),
            "log": [],
            "turns_since_update": 0,
        }
        _doc_ref().set(initial)
        return initial
    data = snap.to_dict() or {}
    data.setdefault("state", json.loads(json.dumps(DEFAULT_STATE)))
    data.setdefault("log", [])
    data.setdefault("turns_since_update", 0)
    return data


def save_campaign(state: dict, log: list, turns_since_update: int) -> None:
    _doc_ref().set(
        {
            "state": state,
            "log": log[-MAX_LOG_ENTRIES:],
            "turns_since_update": turns_since_update,
        }
    )


def apply_patch(state: dict, patch: dict) -> dict:
    for fact in patch.get("new_facts", []) or []:
        if fact and fact not in state["established_facts"]:
            state["established_facts"].append(fact)
    state["inventory"].update(patch.get("inventory_changes", {}) or {})
    state["quest_flags"].update(patch.get("quest_flag_updates", {}) or {})
    state["npc_notes"].update(patch.get("npc_notes", {}) or {})

    state.setdefault("party", {})
    for name, changes in (patch.get("party_updates", {}) or {}).items():
        pc = state["party"].setdefault(name, {})
        if "hp" in changes:
            pc["hp"] = changes["hp"]
        if "coins" in changes:
            pc["coins"] = changes["coins"]
        pc_inventory = pc.setdefault("inventory", [])
        for item in changes.get("inventory_add", []) or []:
            if item not in pc_inventory:
                pc_inventory.append(item)
        for item in changes.get("inventory_remove", []) or []:
            if item in pc_inventory:
                pc_inventory.remove(item)

    return state


def state_as_text(state: dict) -> str:
    return json.dumps(state, indent=2, ensure_ascii=False)
