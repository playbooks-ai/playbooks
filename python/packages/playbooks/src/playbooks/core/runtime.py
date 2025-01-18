import uuid
from typing import Iterator, List, Union

from playbooks.config import RuntimeConfig
from playbooks.core.agents import Agent, AIAgent
from playbooks.core.db.runtime_session import RuntimeSession
from playbooks.core.exceptions import PlaybookError
from playbooks.core.llm_helper import get_completion
from playbooks.core.runtime_log_node import (
    LoadPlaybooksRuntimeLogNode,
    MessageRuntimeLogNode,
    PreprocessPlaybooksRuntimeLogNode,
    RuntimeLogNode,
)
from playbooks.markdown_to_ast import markdown_to_ast

from .loader import load
from .message_router import MessageRouter


class PlaybooksRuntime:
    def __init__(self, config: RuntimeConfig = None):
        self.id = uuid.uuid4()

        self.config = config or RuntimeConfig()
        # Markdown content of all playbooks
        self.playbooks_content: str = None

        # Abstract syntax tree of all playbooks
        self.ast: dict = None

        # List of agents
        self.agents: List[Agent] = []

        # List of runtime log nodes
        self.runtime_log_nodes: List[RuntimeLogNode] = []

        # Runtime session
        self._session = RuntimeSession(runtime=self)
        # save session to DB
        self._session.save()

        # Track previous log node for parent relationship
        self._previous_log_node: RuntimeLogNode = None

        # Mock LLM response
        self._mock_llm_response = None

        # Message router
        self.router = MessageRouter(self)

    def add_runtime_log(self, log_node: RuntimeLogNode) -> RuntimeLogNode:
        """Add a log node and update parent relationship."""
        if self._previous_log_node:
            log_node.parent_log_node_id = self._previous_log_node.id
        self.runtime_log_nodes.append(log_node)
        self._previous_log_node = log_node
        return log_node

    def load_playbooks(self, playbooks: str) -> None:
        self.playbooks_content = playbooks
        self.add_runtime_log(
            LoadPlaybooksRuntimeLogNode.create(
                playbooks_paths=None,
                playbooks=playbooks,
            )
        )

    def load_from_paths(self, playbooks_paths: List[str]) -> None:
        for playbooks_path in playbooks_paths:
            self.load_from_path(playbooks_path)

    def load_from_path(
        self, playbooks_path: str, mock_llm_response: str = None
    ) -> None:
        # Load playbook content using the loader
        log_node = LoadPlaybooksRuntimeLogNode.create(
            playbooks_path=playbooks_path,
            playbooks="",
        )
        self.add_runtime_log(log_node)

        try:
            self.playbooks_content = load([playbooks_path])
            log_node.set_playbooks(self.playbooks_content)
        except FileNotFoundError as e:
            log_node.set_error(f"Playbook not found: {str(e)}")
            raise PlaybookError(f"Playbook not found: {str(e)}") from e
        except (OSError, IOError) as e:
            log_node.set_error(f"Error reading playbook: {str(e)}")
            raise PlaybookError(f"Error reading playbook: {str(e)}") from e

        # Load playbooks
        self.preprocess_playbooks(mock_llm_response)

    def preprocess_playbooks(self, mock_llm_response: str = None):
        self.ast = markdown_to_ast(self.playbooks_content)

        self.add_runtime_log(
            PreprocessPlaybooksRuntimeLogNode.create(
                playbooks=self.playbooks_content,
                metadata={"ast": self.ast},
            )
        )

        self.agents = [
            AIAgent.from_h1(h1)
            for h1 in self.ast.get("children", [])
            if h1.get("type") == "h1"
        ]
        self._mock_llm_response = mock_llm_response

    def _get_completion(self, stream=False, **kwargs):
        return get_completion(
            config=self.config.llm_config,
            mock_response=self._mock_llm_response,
            stream=stream,
            **kwargs,
        )

    def run(
        self, user_message: str = None, stream: bool = False, **kwargs
    ) -> Union[str, Iterator[str]]:
        """Run playbooks using the configured model"""
        if user_message:
            self.add_runtime_log(
                MessageRuntimeLogNode.create(
                    message=user_message,
                    role="user",
                )
            )
        if stream:
            return self.stream(self.playbooks_content, user_message, **kwargs)

        # Get conversation history from kwargs if present, otherwise create initial messages
        messages = kwargs.pop(
            "conversation",
            [
                {"role": "system", "content": self.playbooks_content},
                {"role": "user", "content": user_message or self.playbooks_content},
            ],
        )

        raw_response = self._get_completion(
            messages=messages,
            **kwargs,
        )
        response = raw_response["choices"][0]["message"]["content"]
        self.add_runtime_log(
            MessageRuntimeLogNode.create(
                message=response,
                role="agent",
            )
        )
        return response

    def stream(
        self, system_prompt: str, user_message: str = None, **kwargs
    ) -> Iterator[str]:
        """Run playbooks using the configured model with streaming enabled"""
        # Get conversation history from kwargs if present, otherwise create initial messages
        messages = kwargs.pop(
            "conversation",
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message or ""},
            ],
        )

        response = self._get_completion(
            messages=messages,
            stream=True,
            **kwargs,
        )
        complete_message = ""
        for chunk in response:
            if chunk["choices"][0]["delta"].get("content"):
                content = chunk["choices"][0]["delta"]["content"]
                complete_message += content
                yield content

        # log event after streaming is complete with accumulated message
        self.add_runtime_log(
            MessageRuntimeLogNode.create(
                message=complete_message,
                role="agent",
            )
        )

    def get_llm_completion(self, messages: List[dict]):
        """Get completion from LLM using runtime's config."""
        response_gen = get_completion(
            config=self.config.llm_config,
            messages=messages,
            mock_response=self._mock_llm_response,
            stream=True,  # Always stream internally
        )
        for chunk in response_gen:
            if chunk["choices"][0]["delta"].get("content"):
                yield chunk["choices"][0]["delta"]["content"]

    @property
    def conversation(self) -> List[dict]:
        conversation = []
        print("[DEBUG] Building conversation history from log nodes")
        for log_node in self.runtime_log_nodes:
            if log_node.isinstance(MessageRuntimeLogNode):
                if log_node.role == "user":
                    conversation.append({"role": "user", "content": log_node.message})
                elif log_node.role == "agent":
                    conversation.append(
                        {"role": "assistant", "content": log_node.message}
                    )
        return conversation


class SingleThreadedPlaybooksRuntime(PlaybooksRuntime):
    def run(self, config: RuntimeConfig = None) -> str:
        """Run playbooks."""
        return super().run(config=config or RuntimeConfig())


def run(playbooks: str, **kwargs) -> str:
    """Convenience function to run playbooks"""
    model = kwargs.pop("model", None)
    api_key = kwargs.pop("api_key", None)
    config = RuntimeConfig(model=model, api_key=api_key)
    runtime = SingleThreadedPlaybooksRuntime(config)
    runtime.load_playbooks(playbooks)
    return runtime.run(**kwargs)
