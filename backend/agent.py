import os
from pathlib import Path
from typing import Any, Optional, Dict, List

# Standard Project & Location setup
proj_id = os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or "iron-diet-agent"
loc_id = os.getenv("LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"

os.environ["GOOGLE_CLOUD_PROJECT"] = proj_id
os.environ["GOOGLE_CLOUD_LOCATION"] = loc_id
os.environ["PROJECT_ID"] = proj_id
os.environ["LOCATION"] = loc_id
os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "1"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_API_PREVENT_AGENT_TOKEN_SHARING_FOR_GCP_SERVICES"] = "false"
os.environ["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "false"

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import FunctionTool, agent_tool, url_context, load_memory
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from backend.tools import send_email_notification

# Base directory pointing to skills/ at project root.
# Path(__file__) = /app/backend/agent.py inside the container → parents[1] = /app
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"

# Load ADK Skill Toolset — guard with try/except so skill-path errors surface
# clearly in container logs rather than as an opaque import failure.
try:
    skill_toolset = SkillToolset(
        skills=[
            load_skill_from_dir(SKILLS_DIR / "diet-planner"),
            load_skill_from_dir(SKILLS_DIR / "grocery-list"),
            load_skill_from_dir(SKILLS_DIR / "brand-voice"),
        ],
    )
except Exception as _skill_err:
    raise RuntimeError(
        f"Failed to load skills from {SKILLS_DIR}. "
        f"Ensure the 'skills/' directory was copied into the container image. "
        f"Original error: {_skill_err}"
    ) from _skill_err

# Pipeline Stage Mapping
_TOOL_STAGES = {
    "load_memory": "consulting_memory",
    "Iron_Diet_Agent_google_search_agent": "researching",
    "Iron_Diet_Agent_url_context_agent": "researching",
    "load_skill": "planning",
    "grocerylistagent": "grocery_list",
}


def _init_stage(callback_context: CallbackContext) -> None:
    """Initialize state before turn begins."""
    if "pipeline_stage" not in callback_context.state:
        callback_context.state["pipeline_stage"] = "idea"


def _track_stage(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext, tool_response: Any
) -> Optional[dict]:
    """Update pipeline_stage state based on active tool execution."""
    if tool.name in _TOOL_STAGES:
        tool_context.state["pipeline_stage"] = _TOOL_STAGES[tool.name]
    elif tool.name == "send_email_notification":
        tool_context.state["pipeline_stage"] = "completed"

    return None

async def _stage_after_agent(callback_context: CallbackContext) -> None:
    state = callback_context.state
    if state.get("pipeline_stage") in ("planning", "grocery_list"):
        state["pipeline_stage"] = "awaiting_approval"


# Resolve model name from env (default: gemini-2.5-flash).
# Use plain Gemini() — do NOT subclass — so pickling does not bake in local
# client state/credentials.  The ADK resolves Vertex AI ambient credentials
# dynamically at container runtime.
_MODEL = os.getenv("ORCHESTRATOR_MODEL", "gemini-2.5-flash")

# Sub-agents
grocerylistagent = LlmAgent(
    name="grocerylistagent",
    model=Gemini(model=_MODEL),
    description="Extracts ingredients from weekly meal plans and organizes them into a categorized grocery list.",
    sub_agents=[],
    instruction="Load and follow the `grocery-list` skill to structure the shopping list.",
    tools=[skill_toolset],
)

iron_diet_agent_google_search_agent = LlmAgent(
    name="Iron_Diet_Agent_google_search_agent",
    model=Gemini(model=_MODEL),
    description="Agent specialized in performing Google searches.",
    sub_agents=[],
    instruction="Use the GoogleSearchTool to find information on the web.",
    tools=[GoogleSearchTool()],
)

iron_diet_agent_url_context_agent = LlmAgent(
    name="Iron_Diet_Agent_url_context_agent",
    model=Gemini(model=_MODEL),
    description="Agent specialized in fetching content from URLs.",
    sub_agents=[],
    instruction="Use the UrlContextTool to retrieve content from provided URLs.",
    tools=[url_context],
)

# Root Orchestrator Agent
root_agent = LlmAgent(
    name="Iron_Diet_Agent",
    model=Gemini(model=_MODEL),
    description="A personalized nutrition assistant specializing in iron optimization, custom meal planning, and grocery list generation.",
    sub_agents=[grocerylistagent],
    before_agent_callback=_init_stage,
    after_tool_callback=_track_stage,
    after_agent_callback=_stage_after_agent,
    instruction="""You are the Iron Diet Agent.

Capabilities & Capabilities Mapping:
- You HAVE full operational ability to send emails using the `send_email_notification` tool.
- NEVER claim or state that you lack email sending functionality.

Memory Bank Consulting:
- Before creating meal plans or recommending recipes, ALWAYS consult memory using `load_memory` to retrieve saved user preferences, dietary restrictions, and explicit instructions.

Strict Approval Workflow:
1. Load and follow `brand-voice` for medical disclaimers and tone.
2. When asked for meal plans, load and follow `diet-planner`.
3. When creating shopping lists, hand off to `grocerylistagent` or load `grocery-list`.
4. DRAFTING PHASE: If the user requests sending an email (e.g., "email this to user@example.com"), present the completed meal plan and grocery list in your response FIRST. Do NOT invoke `send_email_notification` in this turn. End your message by explicitly asking: "Would you like me to send this to <email address>?"
5. EXECUTION PHASE: When the user explicitly confirms (e.g., "Yes", "I approve", "Looks good, send it"), IMMEDIATELY execute the `send_email_notification` tool with parameters:
   - `to_email`: The recipient's email address
   - `subject`: A descriptive subject line (e.g., "Your High-Iron Meal Plan & Grocery List")
   - `body`: The full plan and grocery list text
""",
    tools=[
        load_memory,
        skill_toolset,
        agent_tool.AgentTool(agent=iron_diet_agent_google_search_agent),
        agent_tool.AgentTool(agent=iron_diet_agent_url_context_agent),
        FunctionTool(send_email_notification),
    ],
)