import uuid
import uvicorn
from fastapi import FastAPI
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.agent import root_agent

app = FastAPI(title="iron-diet-agent Backend")

# Initialize session service and ADK runner
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="iron-diet-agent"
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "agent": root_agent.name,
        "sub_agents": [sa.name for sa in root_agent.sub_agents]
    }

@app.post("/chat")
async def chat(message: str, session_id: str = "default-session"):
    # Ensure session exists
    session = await session_service.get_session(
        app_name="iron-diet-agent",
        user_id="user",
        session_id=session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name="iron-diet-agent",
            user_id="user",
            session_id=session_id
        )

    # Wrap the string prompt into a Google GenAI Content object
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)]
    )

    response_text = ""
    # Execute the agent through the standard Runner
    async for event in runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=user_content
    ):
        if hasattr(event, "content") and event.content:
            for part in getattr(event.content, "parts", []):
                if hasattr(part, "text") and part.text:
                    response_text += part.text
        elif hasattr(event, "text") and event.text:
            response_text += str(event.text)

    return {"response": response_text or "No text response generated."}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)