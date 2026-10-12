import os
from pathlib import Path
from typing import Any, Optional

# Ensure the Google GenAI SDK targets Vertex AI with Application Default Credentials (ADC)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
if "PROJECT_ID" in os.environ and "GOOGLE_CLOUD_PROJECT" not in os.environ:
    os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ["PROJECT_ID"]
if "LOCATION" in os.environ and "GOOGLE_CLOUD_LOCATION" not in os.environ:
    os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ["LOCATION"]

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.genai import Client
from google.adk.tools import FunctionTool, agent_tool, url_context
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
        is_error = False
        if isinstance(tool_response, dict):
            is_error = tool_response.get("status") == "error" or tool_response.get("isError", False)
        elif isinstance(tool_response, str):
            is_error = "Failed to send" in tool_response or "error" in tool_response.lower()

        if not is_error:
            tool_context.state["pipeline_stage"] = "completed"

    return None


def _stage_after_agent(callback_context: CallbackContext) -> None:
    """Set awaiting approval stage if waiting on user confirmation to email."""
    if callback_context.state.get("pipeline_stage") in ("planning", "grocery_list"):
        callback_context.state["pipeline_stage"] = "awaiting_approval"


class GlobalGemini(Gemini):
    """Clean Gemini model wrapper inheriting cleanly from Gemini without custom
    credential injection, using standard Application Default Credentials (ADC)
    provided automatically by the Vertex AI container runtime.
    """

    def __init__(self, **data: Any):
        if "model" not in data or not data["model"]:
            data["model"] = os.getenv("ORCHESTRATOR_MODEL", "gemini-2.5-flash")
        super().__init__(**data)

    def __reduce__(self):
        func, args, state = super().__reduce__()
        if isinstance(state, dict) and "__dict__" in state:
            d = state["__dict__"].copy()
            d.pop("_per_loop_api_client", None)
            state = dict(state, __dict__=d)
        return (func, args, state)


# Sub-agents
grocerylistagent = LlmAgent(
    name="grocerylistagent",
    model=GlobalGemini(model="gemini-2.5-flash"),
    description="Extracts ingredients from weekly meal plans and organizes them into a categorized grocery list.",
    sub_agents=[],
    instruction="Load and follow the `grocery-list` skill to structure the shopping list.",
    tools=[skill_toolset],
)

iron_diet_agent_google_search_agent = LlmAgent(
    name="Iron_Diet_Agent_google_search_agent",
    model=GlobalGemini(model="gemini-2.5-flash"),
    description="Agent specialized in performing Google searches.",
    sub_agents=[],
    instruction="Use the GoogleSearchTool to find information on the web.",
    tools=[GoogleSearchTool()],
)

iron_diet_agent_url_context_agent = LlmAgent(
    name="Iron_Diet_Agent_url_context_agent",
    model=GlobalGemini(model="gemini-2.5-flash"),
    description="Agent specialized in fetching content from URLs.",
    sub_agents=[],
    instruction="Use the UrlContextTool to retrieve content from provided URLs.",
    tools=[url_context],
)

# Root Orchestrator Agent
root_agent = LlmAgent(
    name="Iron_Diet_Agent",
    model=GlobalGemini(model="gemini-2.5-flash"),
    description="A personalized nutrition assistant specializing in iron optimization, custom meal planning, and grocery list generation.",
    sub_agents=[grocerylistagent],
    before_agent_callback=_init_stage,
    after_tool_callback=_track_stage,
    after_agent_callback=_stage_after_agent,
    instruction="""You are the Iron Diet Agent.

Capabilities & Capabilities Mapping:
- You HAVE full operational ability to send emails using the `send_email_notification` tool.
- NEVER claim or state that you lack email sending functionality.

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
        skill_toolset,
        agent_tool.AgentTool(agent=iron_diet_agent_google_search_agent),
        agent_tool.AgentTool(agent=iron_diet_agent_url_context_agent),
        FunctionTool(send_email_notification),
    ],
)