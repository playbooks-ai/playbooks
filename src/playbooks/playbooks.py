from typing import List

from .loader import Loader
from .program import Program
from .transpiler import Transpiler
from .utils.llm_config import LLMConfig


class Playbooks:
    def __init__(self, program_paths: List[str], llm_config: LLMConfig = None):
        self.program_paths = program_paths
        self.llm_config = llm_config or LLMConfig()
        self.program_content = Loader.read_program(program_paths)
        self.transpiled_program_content = self.transpile_program(self.program_content)
        self.program = Program(self.transpiled_program_content)

    def begin(self):
        self.program.begin()

    def transpile_program(self, program_content: str) -> str:
        transpiler = Transpiler(self.llm_config)
        return transpiler.process(program_content)
