"""Shared helpers for consistent human WaitForMessage behavior across apps."""

import asyncio
from typing import Awaitable, Callable, Optional, Protocol


class _OnWait(Protocol):
    async def __call__(self, agent_self, source_agent_id: str) -> None: ...


class _OnPrompt(Protocol):
    async def __call__(self, agent_self) -> None: ...


def build_human_wait_patch(
    original_wait_for_message: Callable[[object, str], Awaitable],
    *,
    on_wait: Optional[_OnWait] = None,
    on_prompt: Optional[_OnPrompt] = None,
):
    """Return a patched WaitForMessage that blocks for human input.

    on_wait: optional hook invoked before each wait (e.g., broadcast events).
    on_prompt: optional hook to proactively solicit/enqueue human input when none is queued.
    """

    async def patched_wait_for_message(
        agent_self, source_agent_id: str, *, timeout: Optional[float] = None
    ):
        if on_wait:
            await on_wait(agent_self, source_agent_id)

        if source_agent_id in ("human", "user"):
            while True:
                if on_prompt:
                    # Only prompt if nothing is already queued from human/user
                    existing = await agent_self._message_queue.peek(
                        lambda msg: msg.sender_id.id in ("human", "user")
                    )
                    if not existing:
                        await on_prompt(agent_self)

                messages = await original_wait_for_message(
                    agent_self, source_agent_id, timeout=timeout
                )
                if messages:
                    return messages
                # No messages yet; yield to event loop and keep waiting
                await asyncio.sleep(0)

        return await original_wait_for_message(
            agent_self, source_agent_id, timeout=timeout
        )

    return patched_wait_for_message
