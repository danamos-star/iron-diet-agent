from functools import cached_property
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.genai import Client
from google.adk.tools import agent_tool, url_context
from google.adk.tools.google_search_tool import GoogleSearchTool

from backend.prompts import GROCERY_AGENT_INSTRUCTION, ROOT_AGENT_INSTRUCTION
from backend.tools import send_email_notification

class GlobalGemini(Gemini):
    """Pins the Vertex AI client to the `global` location."""
    @cached_property
    def api_client(self) -> Client:
        return Client(vertexai=True, location="global")

# Sub-agent: Grocery List Specialist
grocerylistagent = LlmAgent(
    name='grocerylistagent',
    model=GlobalGemini(model='gemini-2.5-flash'),
    description='Extracts ingredients from weekly meal plans and organizes them into a categorized grocery shopping list sorted by store department.',
    sub_agents=[],
    instruction=GROCERY_AGENT_INSTRUCTION,
    tools=[],
)

# Search Sub-Agent
iron_diet_agent_google_search_agent = LlmAgent(
    name='Iron_Diet_Agent_google_search_agent',
    model=GlobalGemini(model='gemini-2.5-flash'),
    description='Agent specialized in performing Google searches.',
    sub_agents=[],
    instruction='Use the GoogleSearchTool to find information on the web.',
    tools=[GoogleSearchTool()],
)

# URL Context Sub-Agent
iron_diet_agent_url_context_agent = LlmAgent(
    name='Iron_Diet_Agent_url_context_agent',
    model=GlobalGemini(model='gemini-2.5-flash'),
    description='Agent specialized in fetching content from URLs.',
    sub_agents=[],
    instruction='Use the UrlContextTool to retrieve content from provided URLs.',
    tools=[url_context],
)

# Root Orchestrator Agent
root_agent = LlmAgent(
    name='Iron_Diet_Agent',
    model=GlobalGemini(model='gemini-2.5-flash'),
    description='A personalized nutrition assistant specializing in iron optimization, custom meal planning, and grocery list generation.',
    sub_agents=[grocerylistagent],
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[
        agent_tool.AgentTool(agent=iron_diet_agent_google_search_agent),
        agent_tool.AgentTool(agent=iron_diet_agent_url_context_agent),
        send_email_notification,
    ],
)