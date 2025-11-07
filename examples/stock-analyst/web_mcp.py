"""
MCP Server for Web related tools using Serper Dev API
"""

import argparse
import json
import os

import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Web Tools")

QDR_MAP = {
    "all": None,
    "1d": "d",
    "7d": "w",
    "1m": "m",
    "30d": "m",
    "3m": "q",
    "90d": "q",
    "180d": "h",
    "360d": "y",
}


@mcp.tool()
async def search(queries: list[str], date_range: str = "all") -> list:
    """Search the web for the given one or more queries.

    Args:
        queries: One or more queries to search for, e.g. ["TSLA stock price earnings"]
        date_range: Date range to search for, e.g. "all", "1d", "7d", "30d", "90d", "180d", "360d". Use "1d" or "7d" for recent news.

    Returns:
        list: Search results
    """
    if not os.getenv("SERPER_API_KEY"):
        raise ValueError("SERPER_API_KEY is not set")

    api_url = "https://google.serper.dev/search"
    qdr = QDR_MAP[date_range]

    payload = []
    for query in queries:
        payload.append({"q": query, "qdr": qdr})
    payload = json.dumps(payload)

    headers = {
        "X-API-KEY": os.getenv("SERPER_API_KEY"),
        "Content-Type": "application/json",
    }

    response = requests.request("POST", api_url, headers=headers, data=payload)

    return response.json()


@mcp.tool()
async def scrape(url: str) -> dict:
    """Scrape the given URL and return the markdown content.

    Args:
        url: URL to scrape

    Returns:
        dict: Scraped content markdown
    """
    api_url = "https://scrape.serper.dev"

    payload = json.dumps({"url": url, "include_markdown": True})

    headers = {
        "X-API-KEY": os.getenv("SERPER_API_KEY"),
        "Content-Type": "application/json",
    }

    response = requests.request("POST", api_url, headers=headers, data=payload)

    return response.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web MCP Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8888,
        help="Port to run the server on (default: 8888)",
    )
    args = parser.parse_args()

    mcp.run(transport="streamable-http", port=args.port)
