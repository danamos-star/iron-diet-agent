import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from backend.agent import root_agent

# Initialize session service and ADK runner
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    session_service=session_service,
    app_name="iron-diet-agent"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure Vertex AI/Gemini client is pre-warmed on the running loop and pinned."""
    try:
        app.state.client = root_agent.model.api_client
    except Exception:
        pass
    yield


app = FastAPI(title="iron-diet-agent AG-UI backend", lifespan=lifespan)

# Optional raw ADK endpoints mounted at /adk_raw for diagnostic/eval tools
try:
    from google.adk.cli.fast_api import get_fast_api_app
    adk_raw_app = get_fast_api_app(agents_dir=".", web=False)
    app.mount("/adk_raw", adk_raw_app)
except Exception:
    pass


def _extract_prompt_and_session(
    body: Optional[dict],
    query_message: Optional[str] = None,
    query_session_id: Optional[str] = None,
) -> tuple[str, str]:
    """Helper to extract user message and session/thread id from JSON body or query parameters."""
    message = query_message or ""
    session_id = query_session_id or ""

    if isinstance(body, dict):
        if not session_id:
            session_id = body.get("threadId") or body.get("session_id") or ""

        # Parse messages list (AG-UI format: [{"role": "user", "content": "..."}])
        messages = body.get("messages")
        if isinstance(messages, list) and messages:
            for m in reversed(messages):
                if isinstance(m, dict):
                    role = m.get("role")
                    if role in ("user", None):
                        c = m.get("content") or m.get("text")
                        if c:
                            message = str(c)
                            break
                elif isinstance(m, str) and m.strip():
                    message = m
                    break

        # Fallback to single message property
        if not message and "message" in body and body["message"]:
            message = str(body["message"])

    if not session_id:
        session_id = "default-session"

    message = message.strip()
    # Strip any enclosing quotes (e.g. from ?message='...')
    if (message.startswith("'") and message.endswith("'")) or \
       (message.startswith('"') and message.endswith('"')):
        message = message[1:-1].strip()

    return message, session_id


async def _parse_request_body(request: Request) -> Optional[dict]:
    """Safely extracts JSON or body dict from Request."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                return body
        else:
            raw_body = await request.body()
            if raw_body:
                body = json.loads(raw_body)
                if isinstance(body, dict):
                    return body
    except Exception:
        pass
    return None


async def _ag_ui_stream_generator(prompt: str, thread_id: str, run_id: str):
    """Streams AG-UI Server-Sent Events starting with RUN_STARTED and ending with RUN_FINISHED."""
    now_ms = int(time.time() * 1000)
    message_id = f"msg_{uuid.uuid4().hex[:8]}"

    # 1. RUN_STARTED
    yield f"data: {json.dumps({'type': 'RUN_STARTED', 'threadId': thread_id, 'runId': run_id, 'timestamp': now_ms})}\n\n"

    # 2. TEXT_MESSAGE_START
    yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_START', 'messageId': message_id, 'role': 'assistant', 'timestamp': now_ms})}\n\n"

    try:
        # Ensure session exists in the ADK session service
        session = await session_service.get_session(
            app_name="iron-diet-agent",
            user_id="user",
            session_id=thread_id,
        )
        if not session:
            session = await session_service.create_session(
                app_name="iron-diet-agent",
                user_id="user",
                session_id=thread_id,
            )

        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )

        full_text = ""
        async for event in runner.run_async(
            user_id="user",
            session_id=thread_id,
            new_message=user_content,
        ):
            delta = ""
            if hasattr(event, "content") and event.content:
                for part in getattr(event.content, "parts", []):
                    if hasattr(part, "text") and part.text:
                        delta += part.text
            elif hasattr(event, "text") and event.text:
                delta += str(event.text)

            if delta:
                full_text += delta
                yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': delta})}\n\n"

        if not full_text:
            yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_CONTENT', 'messageId': message_id, 'delta': 'No response generated.'})}\n\n"

        # 3. TEXT_MESSAGE_END
        yield f"data: {json.dumps({'type': 'TEXT_MESSAGE_END', 'messageId': message_id})}\n\n"

        # 4. RUN_FINISHED
        finish_ms = int(time.time() * 1000)
        yield f"data: {json.dumps({'type': 'RUN_FINISHED', 'threadId': thread_id, 'runId': run_id, 'timestamp': finish_ms})}\n\n"

    except Exception as exc:
        err_ms = int(time.time() * 1000)
        yield f"data: {json.dumps({'type': 'RUN_ERROR', 'threadId': thread_id, 'runId': run_id, 'error': str(exc), 'timestamp': err_ms})}\n\n"
        yield f"data: {json.dumps({'type': 'RUN_FINISHED', 'threadId': thread_id, 'runId': run_id, 'timestamp': err_ms})}\n\n"


# ---------------------------------------------------------------------------
# AG-UI Router: Mounted at /api/adk, /api/api/adk, and /adk
# ---------------------------------------------------------------------------
ag_ui_router = APIRouter()


@ag_ui_router.get("")
@ag_ui_router.get("/")
async def ag_ui_status():
    return {
        "status": "online",
        "protocol": "ag-ui",
        "agent": root_agent.name,
        "sub_agents": [sa.name for sa in root_agent.sub_agents],
    }


@ag_ui_router.post("")
@ag_ui_router.post("/")
async def ag_ui_endpoint(
    request: Request,
    message: Optional[str] = None,
    session_id: Optional[str] = None,
):
    body = await _parse_request_body(request)
    prompt, thread_id = _extract_prompt_and_session(body, message, session_id)

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="Missing message in AG-UI request. Provide 'messages': [{'role': 'user', 'content': '...'}] or 'message'."
        )

    run_id = (body.get("runId") if isinstance(body, dict) else None) or str(uuid.uuid4())

    return StreamingResponse(
        _ag_ui_stream_generator(prompt, thread_id, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Register AG-UI router across all passthrough route prefixes
app.include_router(ag_ui_router, prefix="/api/adk", tags=["AG-UI"])
app.include_router(ag_ui_router, prefix="/api/api/adk", tags=["AG-UI (Vertex Passthrough)"])
app.include_router(ag_ui_router, prefix="/adk", tags=["AG-UI (Direct)"])


# ---------------------------------------------------------------------------
# Health & Root Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {
        "status": "online",
        "agent": root_agent.name,
        "sub_agents": [sa.name for sa in root_agent.sub_agents],
    }


@app.get("/health")
@app.get("/healthz")
@app.get("/ping")
def health_check():
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Standard /chat Endpoint (JSON & Query Param Support)
# ---------------------------------------------------------------------------
@app.post("/chat")
async def chat(
    request: Request,
    message: Optional[str] = None,
    session_id: Optional[str] = None,
):
    body = await _parse_request_body(request)
    prompt, actual_session_id = _extract_prompt_and_session(body, message, session_id)

    if not prompt:
        raise HTTPException(
            status_code=400,
            detail="Missing 'message' in request body (JSON: {\"message\": \"...\"} or {\"messages\": [...]}) or query parameter (?message=...)."
        )

    # Ensure session exists
    session = await session_service.get_session(
        app_name="iron-diet-agent",
        user_id="user",
        session_id=actual_session_id,
    )
    if not session:
        session = await session_service.create_session(
            app_name="iron-diet-agent",
            user_id="user",
            session_id=actual_session_id,
        )

    user_content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="user",
        session_id=actual_session_id,
        new_message=user_content,
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