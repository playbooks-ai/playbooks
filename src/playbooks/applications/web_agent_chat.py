"""Minimal HTTP host for Playbooks agents."""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List

from playbooks import Playbooks
from playbooks.markdown_playbook_execution import ExecutionFinished
from playbooks.playbook_call import PlaybookCall
from playbooks.session_log import SessionLogItemLevel


class _OutboxWrapper:
    """Session log wrapper that collects messages for the HTTP client."""

    def __init__(self, session_log, queue: asyncio.Queue, agent):
        self._session_log = session_log
        self._queue = queue
        self.agent = agent

    def append(self, msg, level=SessionLogItemLevel.MEDIUM):
        self._session_log.append(msg, level)
        if (
            isinstance(msg, PlaybookCall)
            and msg.playbook_klass == "SendMessage"
            and msg.args
            and msg.args[0] == "human"
        ):
            self._queue.put_nowait(msg.args[1])

    def __getattr__(self, name):
        return getattr(self._session_log, name)

    def __str__(self):
        return self._session_log.__str__()

    def __repr__(self):
        return self._session_log.__repr__()


@dataclass
class _Run:
    playbooks: Playbooks
    outbox: asyncio.Queue[str]
    task: asyncio.Task
    main_agent: any
    terminated: bool = False


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str = "", content_type: str = "text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        if body:
            self.wfile.write(body.encode())

    def do_POST(self):
        if self.path == "/runs/new":
            self._handle_new_run()
            return
        if self.path.startswith("/runs/") and self.path.endswith("/messages"):
            self._handle_run_message()
            return
        self._send(404, "Not Found")

    def _handle_new_run(self) -> None:
        session_id = str(uuid.uuid4())
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length)) if length else {}
        path = data.get("path")
        program = data.get("program")
        if (path is None and program is None) or (path and program):
            self._send(400, "Specify either 'path' or 'program'")
            return
        try:
            if path:
                playbooks = Playbooks([path], session_id=session_id)
            else:
                playbooks = Playbooks.from_string(program, session_id=session_id)
        except Exception as e:  # pragma: no cover - invalid input
            self._send(400, str(e))
            return

        outbox: asyncio.Queue[str] = asyncio.Queue()

        for agent in playbooks.program.agents:
            # Wrap the session log to capture messages for the HTTP client
            agent.state.session_log = _OutboxWrapper(
                agent.state.session_log, outbox, agent
            )

        task = self.server.loop.create_task(
            _run_program(playbooks, self.server, session_id)
        )
        self.server.runs[session_id] = _Run(
            playbooks, outbox, task, playbooks.program.agents[0]
        )

        # Give the program a moment to start and potentially produce output
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.1), self.server.loop).result()

        # Collect any initial messages
        msgs: List[str] = []
        while not outbox.empty():
            msgs.append(outbox.get_nowait())

        body = json.dumps(
            {
                "session_id": session_id,
                "messages": msgs,
                "terminated": self.server.runs[session_id].terminated,
            }
        )
        self._send(200, body, "application/json")

    def _handle_run_message(self) -> None:
        parts = self.path.strip("/").split("/")
        if len(parts) != 3:
            self._send(404, "Not Found")
            return
        session_id = parts[1]
        run = self.server.runs.get(session_id)
        if not run:
            self._send(404, "Run not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length)) if length else {}
        message = data.get("message")
        if not message:
            self._send(400, "Missing message")
            return
        asyncio.run_coroutine_threadsafe(
            run.playbooks.program.route_message("human", run.main_agent.id, message),
            self.server.loop,
        ).result()
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.1), self.server.loop).result()
        msgs: List[str] = []
        while not run.outbox.empty():
            msgs.append(run.outbox.get_nowait())
        body = json.dumps(
            {"session_id": session_id, "messages": msgs, "terminated": run.terminated}
        )
        self._send(200, body, "application/json")

    def log_message(self, format, *args):  # noqa: D401
        return


class _Server(ThreadingHTTPServer):
    def __init__(self, addr, handler, loop):
        super().__init__(addr, handler)
        self.loop = loop
        self.runs: Dict[str, _Run] = {}


async def _run_program(playbooks, server, session_id):
    try:
        await playbooks.program.begin()
    except ExecutionFinished:
        server.runs[session_id].terminated = True
    except Exception:
        server.runs[session_id].terminated = True
        raise


def main(port: int) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = _Server(("", port), _Handler, loop)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    print(f"Playbooks Agent Chat application server started at http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    try:
        loop.run_forever()
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Playbooks Agent Chat web application server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Playbooks Agent Chat web application server is a simple HTTP server that enables interactive conversations between human users and AI agents through playbooks programs. It provides a REST API interface for:

- Creating new chat sessions with playbooks programs
- Sending messages to AI agents
- Receiving responses from AI agents

The server supports playbooks programs that use:
- A single human agent (the user)
- One or more AI agents

Each chat session is identified by a unique run ID, allowing multiple concurrent conversations. The server maintains the state of each conversation until it's completed or terminated.

IMPORTANT: This server is intended for development and testing purposes only. It is not suitable for production use. For production-grade deployments, please use Playbooks Enterprise Edition which provides:
- Robust process management and recovery
- Horizontal scaling capabilities

Examples:
  # Run server on default port 8000
  python -m playbooks.applications.web_agent_chat

  # Run server on custom port
  python -m playbooks.applications.web_agent_chat --port 9000

API Endpoints:
  POST /runs/new
    Create a new chat session with either:
    - path: Path to a playbook file
    - program: Playbook program content as string
    
    Example:
    curl -X POST http://localhost:8000/runs/new \\
         -H "Content-Type: application/json" \\
         -d '{"path": "tests/data/02-personalized-greeting.pb"}'
    
    Response:
    {
        "session_id": "uuid-of-the-run",
        "messages": ["message1", "message2", ...],
        "terminated": false
    }
    
  POST /runs/{session_id}/messages
    Send a message to an existing chat session
    - message: The message content to send
    
    Example:
    curl -X POST http://localhost:8000/runs/6de12fab-f26a-4a90-88e2-02f4f16dfa39/messages \\
         -H "Content-Type: application/json" \\
         -d '{"message": "Amol"}'
    
    Response:
    {
        "session_id": "uuid-of-the-run",
        "messages": ["message1", "message2", ...],
        "terminated": false
    }

Response Format:
  All responses are JSON objects with the following fields:
  - session_id: string - The unique identifier for this chat session
  - messages: array of strings - List of messages from AI agents since the last request
  - terminated: boolean - Indicates if the program has terminated (true) or is still running (false)
""",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port number to run the HTTP server on (default: 8000)",
    )
    args = parser.parse_args()
    main(args.port)
