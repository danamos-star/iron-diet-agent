# Root-level agent.py — required by the ADK agent loader convention.
#
# The ADK api_server discovers `root_agent` by looking for it in:
#   agents/{app_name}/agent.py   (after copying the project into a temp directory)
#
# This file re-exports `root_agent` from the canonical backend module so the
# loader finds it regardless of which code-path the agent is started from.
from backend.agent import root_agent  # noqa: F401  (re-export)
