"""Output formatting utilities for the CLI."""
from typing import AsyncIterator

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

console = Console()


def print_markdown(text: str):
    """Print text as markdown using rich"""
    md = Markdown(text)
    console.print(md)


async def print_streaming_markdown(stream_iterator: AsyncIterator[str]):
    """Print streaming markdown content"""
    content = ""
    with Live(Markdown(content), refresh_per_second=10) as live:
        async for chunk in stream_iterator:
            content += chunk
            live.update(Markdown(content))
