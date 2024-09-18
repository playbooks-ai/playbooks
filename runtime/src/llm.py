from litellm import completion
from typing import List, Dict, Generator

class LLM:
    def __init__(self, model: str = "anthropic/claude-3-sonnet-20240229"):
        self.model = model

    def create_chat_session(self, system_prompt: str) -> List[Dict[str, str]]:
        return [{"role": "system", "content": system_prompt}]

    def chat(self, session: List[Dict[str, str]], message: str) -> Generator[str, None, None]:
        session.append({"role": "user", "content": message})
        
        stream = completion(
            model=self.model,
            messages=session,
            stream=True
        )

        full_response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_response += content
                yield content

        session.append({"role": "assistant", "content": full_response})
