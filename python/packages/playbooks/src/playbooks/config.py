import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# Default model to use if not specified
DEFAULT_MODEL = os.getenv("MODEL", "claude-3-5-sonnet-20241022")


@dataclass
class LLMConfig:
    model: str = None
    api_key: Optional[str] = None

    def __post_init__(self):
        self.model = self.model or os.environ.get("MODEL") or DEFAULT_MODEL
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")


@dataclass
class RuntimeConfig:
    model: str = None
    api_key: Optional[str] = None
    llm_config: Optional[LLMConfig] = None

    def __post_init__(self):
        self.llm_config = self.llm_config or LLMConfig(
            model=self.model, api_key=self.api_key
        )
