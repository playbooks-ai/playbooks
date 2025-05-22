import os
import uuid
from typing import List

from playbooks.event_bus import EventBus
from playbooks.utils.markdown_to_ast import (
    parse_markdown_to_dict,
    refresh_markdown_attributes,
)

from .loader import Loader
from .program import Program
from .transpiler import Transpiler
from .utils.llm_config import LLMConfig


class Playbooks:
    def __init__(
        self,
        program_paths: List[str],
        llm_config: LLMConfig = None,
        session_id: str = None,
    ):
        self.program_paths = program_paths
        self.llm_config = llm_config or LLMConfig()
        self.session_id = session_id or str(uuid.uuid4())
        self.program_content = Loader.read_program(program_paths)
        self.program_content = self.preprocess_program(self.program_content)
        self.transpiled_program_content = self.transpile_program(self.program_content)
        self.event_bus = EventBus(self.session_id)
        self.program = Program(self.transpiled_program_content, self.event_bus)

    def begin(self):
        self.program.begin()

    def transpile_program(self, program_content: str) -> str:
        transpiler = Transpiler(self.llm_config)
        return transpiler.process(program_content)

    def preprocess_program(self, program_content: str) -> str:
        edited = False
        ast = parse_markdown_to_dict(program_content)
        h2s = filter(
            lambda child: child["type"] == "h2",
            ast.get("children", []),
        )
        for h2 in h2s:
            h3s = list(
                filter(
                    lambda child: child["type"] == "h3"
                    and child.get("text", "").strip().lower() == "steps",
                    h2.get("children", []),
                )
            )
            if not h3s:
                with open(
                    os.path.join(
                        os.path.dirname(__file__), "prompts", "react_steps.md"
                    ),
                    "r",
                ) as f:
                    react_steps = f.read()
                    steps_h3 = parse_markdown_to_dict(react_steps)
                    h2["children"].append(steps_h3)
                    edited = True

        if edited:
            refresh_markdown_attributes(ast)
            program_content = ast["markdown"]

        return program_content
