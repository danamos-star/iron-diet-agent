import os
import uuid
import uvicorn
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.agent import root_agent

app = FastAPI(title="iron-diet-agent Backend")

# Mount AG-UI AGENT endpoint at /api/adk if available
try:
    from google.adk.cli.fast_api import get_fast_api_app
    adk_app = get_fast_api_app(agents_dir=".", web=False)
    app.mount("/api/adk", adk_app)
except Exception:
    pass

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

@app.get("/health")
@app.get("/healthz")
@app.get("/ping")
def health_check():
    return {"status": "healthy"}

@app.post("/chat")
async def chat(
    request: Request,
    message: Optional[str] = None,
    session_id: Optional[str] = None,
):
    actual_message = message
    actual_session_id = session_id

    # Check request body for JSON or raw text payload
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                if not actual_message:
                    actual_message = body.get("message")
                if not actual_session_id:
                    actual_session_id = body.get("session_id")
        else:
            raw_body = await request.body()
            if raw_body:
                import json
                try:
                    body = json.loads(raw_body)
                    if isinstance(body, dict):
                        if not actual_message:
                            actual_message = body.get("message")
                        if not actual_session_id:
                            actual_session_id = body.get("session_id")
                except Exception:
                    if not actual_message:
                        actual_message = raw_body.decode("utf-8", errors="ignore").strip()
    except Exception:
        pass

    if not actual_session_id:
        actual_session_id = "default-session"

    if not actual_message or not actual_message.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing 'message' in request body (JSON: {\"message\": \"...\"}) or query parameter (?message=...)."
        )

    actual_message = actual_message.strip()
    # Strip any enclosing quotes (e.g. from ?message='...')
    if (actual_message.startswith("'") and actual_message.endswith("'")) or \
       (actual_message.startswith('"') and actual_message.endswith('"')):
        actual_message = actual_message[1:-1]

    # Ensure session exists
    session = await session_service.get_session(
        app_name="iron-diet-agent",
        user_id="user",
        session_id=actual_session_id
    )
    if not session:
        session = await session_service.create_session(
            app_name="iron-diet-agent",
            user_id="user",
            session_id=actual_session_id
        )

    # Wrap the string prompt into a Google GenAI Content object
    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=actual_message)]
    )

    response_text = ""
    # Execute the agent through the standard Runner
    async for event in runner.run_async(
        user_id="user",
        session_id=actual_session_id,
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
    port = int(os.environ.get("PORT", os.environ.get("AIP_HTTP_PORT", 8080)))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)