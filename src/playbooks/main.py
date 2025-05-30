import uuid
from typing import List

from .compiler import Compiler
from .event_bus import EventBus
from .loader import Loader
from .program import Program
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
        self.program_content, self.do_not_compile = Loader.read_program(program_paths)

        # Skip compilation if any of the files are already compiled (.pbc)
        if self.do_not_compile:
            # For compiled files, use the content as-is without compilation
            self.compiled_program_content = self.program_content
        else:
            # For source files, compile the program content
            self.compiled_program_content = self.compile_program(self.program_content)

        self.event_bus = EventBus(self.session_id)
        self.program = Program(
            self.compiled_program_content, self.event_bus, program_paths
        )

    def begin(self):
        self.program.begin()

    def compile_program(self, program_content: str) -> str:
        compiler = Compiler(self.llm_config)
        return compiler.process(program_content)
