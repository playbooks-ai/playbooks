import asyncio
import base64
import json
import os
import pickle
from typing import Any, Dict, Optional

from database import SessionLocal, engine
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from litellm.exceptions import (
    InternalServerError,
    ServiceUnavailableError,
)
from models import Base, UserSession
from playbooks.config import DEFAULT_MODEL
from playbooks.core.runtime import RuntimeConfig, SingleThreadedPlaybooksRuntime
from pydantic import BaseModel, ConfigDict
from session import SessionMiddleware

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Error creating database tables: {e}")
    # Don't fail startup, tables will be created on first request

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

DEFAULT_BEGIN_USER_MESSAGE = "Begin"
app = FastAPI(title="Playbooks API")

# Configure CORS for development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development server
        "https://playbooks-frontend.onrender.com",  # Production frontend
        "https://runplaybooks.ai",  # Production domain
    ],
    allow_credentials=True,  # This is crucial for cookies
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["*"],  # Added to ensure all headers are exposed
)

# Add session middleware
app.add_middleware(SessionMiddleware)


class PlaybookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    model: Optional[str] = DEFAULT_MODEL
    llm_options: Optional[Dict[str, Any]] = None
    stream: Optional[bool] = False


class PlaybookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str
    model: Optional[str] = DEFAULT_MODEL
    llm_options: Optional[Dict[str, Any]] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result: str


async def retry_with_exponential_backoff(func, max_retries=3, initial_delay=1):
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func()
        except (InternalServerError, ServiceUnavailableError) as e:
            last_exception = e
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                print(
                    f"[DEBUG] API temporarily unavailable, retrying in {delay} seconds..."
                )
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff

    raise last_exception  # If all retries failed, raise the last exception


def save_session_state(session_id: str, runtime, db=None) -> None:
    """Save runtime state to session.

    Args:
        session_id: The session ID to save state for
        runtime: The runtime object to save
        db: Optional database session. If not provided, a new one will be created.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        session = (
            db.query(UserSession).filter(UserSession.session_id == session_id).first()
        )
        if session:
            runtime_data = base64.b64encode(pickle.dumps(runtime)).decode("utf-8")
            session.runtime_data = runtime_data
            db.commit()
            print("[DEBUG] Stored runtime in session.runtime_data")
            print("events", runtime.events)
    finally:
        if should_close_db:
            db.close()


@app.post("/api/run-playbook", response_model=PlaybookResponse)
async def run_playbook(request: Request, playbook_request: PlaybookRequest):
    try:
        print("[DEBUG] Starting run_playbook")
        config = RuntimeConfig(model=playbook_request.model)
        runtime = SingleThreadedPlaybooksRuntime(config)

        # Load playbook content into runtime
        runtime.load_playbooks(playbook_request.content)
        print("[DEBUG] Loaded playbooks into runtime")

        # Add initial begin message to events
        runtime.events.append(
            {"type": "user_message", "message": DEFAULT_BEGIN_USER_MESSAGE}
        )

        # Store runtime in session
        request.state.session.runtime = runtime
        print("[DEBUG] Stored runtime in session.runtime")

        # Save initial state
        save_session_state(request.state.session.session_id, runtime)

        # Get session_id for async operations
        session_id = request.state.session.session_id

        if playbook_request.stream:
            chunks = []

            async def stream_response():
                async for chunk in runtime.stream(
                    playbook_request.content,
                    user_message=DEFAULT_BEGIN_USER_MESSAGE,
                    **(playbook_request.llm_options or {}),
                ):
                    if chunk.strip():
                        chunks.append(chunk)
                        yield f"data: {json.dumps({'content': chunk})}\n\n"

                # After all chunks are collected, save the state
                # Note: runtime.stream() already adds the agent_message event
                save_session_state(session_id, runtime)
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        else:
            result = await runtime.run(
                playbook_request.content,
                user_message=DEFAULT_BEGIN_USER_MESSAGE,
                **(playbook_request.llm_options or {}),
            )
            # Note: runtime.run() already adds the agent_message event
            # For non-streaming, we can use the existing db connection
            request.state.session.runtime_data = base64.b64encode(
                pickle.dumps(runtime)
            ).decode("utf-8")
            request.state.db.commit()
            return PlaybookResponse(result=result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: Request, chat_request: ChatRequest):
    try:
        print("[DEBUG] Starting chat request")
        # Check if runtime exists in session or load from persistent storage
        session = request.state.session
        runtime = None

        if hasattr(session, "runtime"):
            print("[DEBUG] Found runtime in session.runtime")
            runtime = session.runtime
            print(f"[DEBUG] Runtime events from session.runtime: {runtime.events}")
        elif session.runtime_data:
            print("[DEBUG] Found runtime in session.runtime_data, attempting to load")
            try:
                runtime_data = base64.b64decode(session.runtime_data.encode("utf-8"))
                runtime = pickle.loads(runtime_data)
                session.runtime = runtime
                print("[DEBUG] Successfully loaded runtime from runtime_data")
                print(
                    f"[DEBUG] Runtime events after loading from runtime_data: {runtime.events}"
                )
            except Exception as e:
                print(f"[DEBUG] Failed to load runtime from storage: {e}")

        if not runtime:
            print("[DEBUG] No runtime found in session or storage")
            raise HTTPException(
                status_code=400,
                detail="No active runtime found. Please load a playbook first.",
            )

        # Add current message
        conversation = []
        print("[DEBUG] Building conversation history from events")
        for event in runtime.events:
            if event["type"] == "user_message":
                conversation.append({"role": "user", "content": event["message"]})
            elif event["type"] == "agent_message":
                conversation.append({"role": "assistant", "content": event["message"]})

        # Add current message
        conversation.append({"role": "user", "content": chat_request.message})
        runtime.events.append({"type": "user_message", "message": chat_request.message})
        # Save user message
        save_session_state(request.state.session.session_id, runtime)

        if chat_request.stream:

            async def stream_response():
                chunks = []
                try:
                    # Create a new database session for the streaming response
                    db = SessionLocal()
                    try:
                        session = (
                            db.query(UserSession)
                            .filter(
                                UserSession.session_id
                                == request.state.session.session_id
                            )
                            .first()
                        )

                        async for chunk in runtime.stream(
                            chat_request.message,
                            conversation=conversation,
                            **(chat_request.llm_options or {}),
                        ):
                            if chunk.strip():
                                chunks.append(chunk)
                                yield f"data: {json.dumps({'content': chunk})}\n\n"

                        # After stream is complete, save the state
                        # Note: runtime.stream() already adds the agent_message event
                        runtime_data = base64.b64encode(pickle.dumps(runtime)).decode(
                            "utf-8"
                        )
                        session.runtime_data = runtime_data
                        session.update_activity()
                        db.commit()
                        yield "data: [DONE]\n\n"
                    finally:
                        db.close()

                except (InternalServerError, ServiceUnavailableError) as e:
                    error_msg = f"API temporarily unavailable: {str(e)}"
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    raise HTTPException(status_code=503, detail=error_msg)

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        else:
            raw_response = await retry_with_exponential_backoff(
                lambda: runtime.run(
                    chat_request.message,
                    conversation=conversation,
                    **(chat_request.llm_options or {}),
                )
            )
            response = raw_response["choices"][0]["message"]["content"]
            # Note: runtime.run() already adds the agent_message event
            # Save state after the response
            save_session_state(request.state.session.session_id, runtime)
            return ChatResponse(result=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/examples/{filename}")
async def get_example(filename: str):
    try:
        # Check for directory traversal in filename before constructing path
        if os.path.isabs(filename) or ".." in os.path.normpath(filename):
            raise HTTPException(status_code=400, detail="Invalid filename")

        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "python/packages/playbooks/examples/playbooks",
        )
        file_path = os.path.join(examples_dir, filename)
        # Double check path is within examples directory
        norm_file_path = os.path.normpath(file_path)
        norm_examples_dir = os.path.normpath(examples_dir)
        if not norm_file_path.startswith(norm_examples_dir):
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Check for file existence after security checks
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                content = f.read()
            return {"content": content}
        else:
            raise HTTPException(status_code=404, detail="Example Not Found")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}
