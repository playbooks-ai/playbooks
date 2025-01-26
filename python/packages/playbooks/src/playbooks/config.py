import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from .constants import DEFAULT_MODEL

load_dotenv()


@dataclass
class LLMConfig:
    model: str = None
    api_key: Optional[str] = None

    def __post_init__(self):
        self.model = self.model or os.environ.get("MODEL") or DEFAULT_MODEL
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
