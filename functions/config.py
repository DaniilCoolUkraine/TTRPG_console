"""Central place to tune models, context size, and update cadence.

Identical to the local-script version — nothing here is specific to
running inside Cloud Functions.
"""

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
STRONG_MODEL = "claude-sonnet-5"
SCRIBE_MODEL = "claude-haiku-4-5-20251001"

# How many recent log entries (DM lines + PC replies) to feed as live,
# uncached context on top of the cached rules doc + state file.
RECENT_MESSAGE_WINDOW = 14

# How many full rounds (one DM line + all PCs replying) happen between
# automatic scribe updates. force_update() can also trigger one anytime.
AUTO_UPDATE_EVERY_N_TURNS = 4

MAX_OUTPUT_TOKENS = 600
