import time
from typing import List

from litellm import token_counter

from .config import LLMConfig
from .trace_mixin import TraceMixin
from .utils.llm_helper import get_completion


class LLMCall(TraceMixin):
    def __init__(
        self,
        llm_config: LLMConfig,
        messages: List[dict],
        stream: bool,
        json_mode: bool = False,
    ):
        super().__init__()
        self.llm_config: LLMConfig = llm_config
        self.messages: List[dict] = messages
        self.stream: bool = stream
        self.json_mode: bool = json_mode

    def __repr__(self):
        return f"LLMCall({self.llm_config.model})"

    def execute(self):
        response = []
        start_time = time.time()
        first_token_time = None
        token_usage = 0

        for chunk in get_completion(
            llm_config=self.llm_config,
            messages=self.messages,
            stream=self.stream,
            json_mode=self.json_mode,
        ):
            if chunk is not None:
                if first_token_time is None:
                    first_token_time = time.time()
                response.append(chunk)
                token_usage += len(chunk.split())
                yield chunk

        end_time = time.time()
        time_to_first_token = (
            first_token_time - start_time if first_token_time else None
        )
        total_time = end_time - start_time
        response_str = "".join(response)

        self.trace(
            "Success",
            metadata={
                "llm_config": self.llm_config.to_dict(),
                "messages": self.messages,
                "stream": self.stream,
                "time_to_first_token_ms": (
                    time_to_first_token * 1000 if time_to_first_token else None
                ),
                "response": response_str,
                "total_time_ms": total_time * 1000,
                "input_tokens": token_counter(
                    model=self.llm_config.model, messages=self.messages
                ),
                "output_tokens": token_counter(
                    model=self.llm_config.model,
                    messages=[{"content": response_str}],
                ),
            },
        )
        return response
