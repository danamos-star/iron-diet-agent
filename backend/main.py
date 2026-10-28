import asyncio
import json
import logging
import os
import re
import time
import uuid
from typing import Optional

import uvicorn
import vertexai
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, VertexAiSessionService
from google.adk.memory import InMemoryMemoryService, VertexAiMemoryBankService
from google.genai import types

from backend.agent import root_agent

logger = logging.getLogger("backend.main")
logger.warning("[Startup] build marker: save-direct-v2")

USER_ID = "user"  # TODO: take a real per-user ID from the request

# ---------------------------------------------------------------------------
# Dynamic Session Service & Memory Bank Initialization
# ---------------------------------------------------------------------------
app_url = os.getenv("APP_URL", "")
app_url_pattern = r"projects/([^/]+)/locations/([^/]+)/reasoningEngines/([^/]+)"
match = re.search(app_url_pattern, app_url)

if match:
    # Running inside GCP Agent Runtime
    project_number, location, engine_id = match.groups()
    app_name = engine_id
    session_service = VertexAiSessionService(
        project=project_number,
        location="us-central1",
    )
    memory_service = VertexAiMemoryBankService(
        project=project_number,
        location="us-central1",
        agent_engine_id=engine_id,
    )
else:
    # Running locally
    app_name = "iron-diet-agent"
    session_service = InMemorySessionService()
    memory_service = InMemoryMemoryService()

runner = Runner(
    agent=root_agent,
    session_service=session_service,
    memory_service=memory_service,
    app_name=app_name,
)

app = FastAPI(title="iron-diet-agent AG-UI backend")

# Optional raw ADK endpoints mounted at /adk_raw for diagnostic/eval tools
try:
    from google.adk.cli.fast_api import get_fast_api_app
    adk_raw_app = get_fast_api_app(agents_dir=".", web=False)
    app.mount("/adk_raw", adk_raw_app)
except Exception:
    pass


# ---------------------------------------------------------------------------
# Memory Bank: save a finished turn directly (bypasses ADK's background task)
# ---------------------------------------------------------------------------
async def persist_memory(thread_id: str, user_id: str = USER_ID) -> None:
    """Re-fetch the session, then ask Memory Bank to generate memories from it."""
    if not match:  # local mode, no Memory Bank
        return

    try:
        final_session = await session_service.get_session(
            app_name=app_name, user_id=user_id, session_id=thread_id
        )
    except Exception:
        logger.exception("[MemoryBank] get_session FAILED")
        return
    if not final_session:
        logger.warning("[MemoryBank] session not found for thread=%s", thread_id)
        return

    logger.warning(
    "[MemoryBank] ids: thread=%s session.id=%s events=%d",
    thread_id,
    final_session.id,
    len(final_session.events or [])
)