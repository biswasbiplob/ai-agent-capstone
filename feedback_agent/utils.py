import asyncio
import uuid
from typing import Any, Optional, Dict
from google.adk.agents.llm_agent import Agent
from google.adk.sessions.session import Session
from google.adk.events.event import Event
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types
from google.adk.agents.run_config import RunConfig
from google.adk.sessions.base_session_service import BaseSessionService, GetSessionConfig, ListSessionsResponse

class MockSessionService(BaseSessionService):
    async def create_session(self, *, app_name: str, user_id: str, state: Optional[dict[str, Any]] = None, session_id: Optional[str] = None) -> Session:
        return Session(id=session_id or "mock-session", app_name=app_name, user_id=user_id)

    async def get_session(self, *, app_name: str, user_id: str, session_id: str, config: Optional[GetSessionConfig] = None) -> Optional[Session]:
        return None

    async def list_sessions(self, *, app_name: str, user_id: Optional[str] = None) -> ListSessionsResponse:
        return ListSessionsResponse()

    async def delete_session(self, *, app_name: str, user_id: str, session_id: str) -> None:
        pass

import threading
import queue

import logging

# Configure logging
logger = logging.getLogger(__name__)


def run_agent(
    agent: Agent,
    input_text: str,
    image_path: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    session_state: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Synchronous wrapper for running an agent.
    Handles creating a fresh event loop in a separate thread if needed.
    """
    result_queue: queue.Queue[object] = queue.Queue()

    def target():
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_run_agent_async(agent, input_text, image_path, image_bytes, session_state))
            result_queue.put(result)
            loop.close()
        except Exception as e:
            result_queue.put(e)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()

    result = result_queue.get()
    if isinstance(result, Exception):
        raise result
    if not isinstance(result, str):
        raise TypeError(f"Expected string result, got {type(result)}")
    return result

async def _run_agent_async(
    agent: Agent,
    prompt: str,
    image_path: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    session_state: Optional[Dict[str, Any]] = None,
) -> str:
    # 1. Create Session
    session_id = str(uuid.uuid4())
    session = Session(id=session_id, app_name="feedback_agent", user_id="user")
    
    # 2. Create User Event
    parts = [types.Part(text=prompt)]
    
    if image_path:
        # Read image and create part
        # Note: This depends on how types.Part supports images. 
        # Usually it's inline_data or file_data.
        with open(image_path, "rb") as f:
            image_data = f.read()
        parts.append(types.Part(inline_data=types.Blob(data=image_data, mime_type="image/jpeg")))
    elif image_bytes:
        parts.append(types.Part(inline_data=types.Blob(data=image_bytes, mime_type="image/jpeg")))

    content = types.Content(parts=parts)

    # Create a mock session service
    session_service = MockSessionService()
    
    # Create InvocationContext
    invocation_id = str(uuid.uuid4())
    context = InvocationContext(
        agent=agent,
        session=session,
        invocation_id=str(uuid.uuid4()),
        user_content=types.Content(parts=[types.Part(text=prompt)]), # Changed from 'content' to 'types.Content(parts=[types.Part(text=prompt)])'
        session_service=session_service,
        run_config=RunConfig()
    )
    print(f"DEBUG: InvocationContext created. User Content: {context.user_content}")
    
    # Inject session state if provided
    if session_state:
        if context.session.state is None:
            context.session.state = {}
        context.session.state.update(session_state)

    # Run the agent
    response_text = ""
    async for event in agent.run_async(context):
        if event.actions and event.actions.state_delta:
            if context.session.state is None:
                context.session.state = {}
            context.session.state.update(event.actions.state_delta)
            
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_text += part.text
    
    return response_text
