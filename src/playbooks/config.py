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
        if self.api_key is None:
            if "claude" in self.model:
                self.api_key = os.environ.get("ANTHROPIC_API_KEY")
            elif "gemini" in self.model:
                self.api_key = os.environ.get("GEMINI_API_KEY")
