"""Chat session management for the CLI."""
import uuid
from typing import List, Optional

from rich.console import Console

from playbooks.core.loader import load
from playbooks.core.runtime import RuntimeConfig, SingleThreadedPlaybooksRuntime
from playbooks.core.state import StateManager
from playbooks.cli.output import print_markdown, print_streaming_markdown

console = Console()
state_manager = StateManager()


class ChatSession:
    """Manages a chat session with playbooks runtime."""

    def __init__(
        self,
        playbook_paths: List[str],
        llm: Optional[str],
        model: Optional[str],
        api_key: Optional[str],
        stream: bool,
    ):
        self.playbook_paths = playbook_paths
        self.llm = llm
        self.model = model
        self.api_key = api_key
        self.stream = stream
        self.session_id = str(uuid.uuid4())
        self.runtime = None
        self.playbooks_content = None

    async def initialize(self):
        """Initialize the chat session by loading playbooks and setting up runtime"""
        console.print(f"\nLoading playbooks from: {self.playbook_paths}")
        self.playbooks_content = load(self.playbook_paths)
        console.print("\nLoaded playbooks successfully")

        console.print(
            f"\nInitializing runtime with model={self.model}, "
            f"api_key={'*' * len(self.api_key) if self.api_key else None}"
        )
        config = RuntimeConfig(model=self.model, api_key=self.api_key)
        self.runtime = SingleThreadedPlaybooksRuntime(config)
        self.runtime.events = [{"type": "user_message", "message": "Begin"}]
        state_manager.save_state(self.session_id, self.runtime)
        console.print("\nRuntime initialized successfully")

    def _get_conversation(self) -> List[dict]:
        """Convert events list to conversation format for LLM"""
        conversation = [{"role": "system", "content": self.playbooks_content}]
        for event in self.runtime.events:
            if event["type"] == "user_message":
                conversation.append({"role": "user", "content": event["message"]})
            elif event["type"] == "assistant_message":
                conversation.append({"role": "assistant", "content": event["message"]})
        return conversation

    async def _handle_streaming_response(self, user_input: str):
        """Handle streaming response from LLM"""
        response_stream = self.runtime.stream(
            self.playbooks_content,
            user_message=user_input,
            conversation=self._get_conversation(),
        )
        await print_streaming_markdown(response_stream)
        self.runtime.events.append(
            {"type": "assistant_message", "message": self.runtime.events[-1]["message"]}
        )

    async def _handle_non_streaming_response(self, user_input: str):
        """Handle non-streaming response from LLM"""
        response = await self.runtime.run(
            self.playbooks_content,
            user_message=user_input,
            conversation=self._get_conversation(),
        )
        print_markdown(response)
        self.runtime.events.append({"type": "assistant_message", "message": response})

    async def process_user_input(self, user_input: str) -> bool:
        """Process user input and return False if session should end"""
        if user_input.lower() in ["exit", "quit"]:
            console.print("\nExiting chat loop...")
            self.cleanup()
            return False

        try:
            self.runtime.events.append({"type": "user_message", "message": user_input})
            console.print("\n[yellow]Agent: [/yellow]")

            if self.stream:
                await self._handle_streaming_response(user_input)
            else:
                await self._handle_non_streaming_response(user_input)

            state_manager.save_state(self.session_id, self.runtime)
            return True

        except Exception as e:
            console.print(f"\n[red]Error processing response:[/red] {str(e)}")
            raise

    def cleanup(self):
        """Clean up session resources"""
        state_manager.clear_state(self.session_id)
