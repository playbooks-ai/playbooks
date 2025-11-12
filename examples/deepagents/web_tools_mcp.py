"""
Web Tools MCP Server for DeepAgent Playbooks
Provides web search, URL fetching, and HTTP request capabilities
"""

import os
from typing import Any, Dict, Literal, Optional

import requests
from fastmcp import FastMCP
from markdownify import markdownify

# Initialize Tavily client if API key is available
try:
    from tavily import TavilyClient

    tavily_client = (
        TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
        if os.environ.get("TAVILY_API_KEY")
        else None
    )
except ImportError:
    tavily_client = None

mcp = FastMCP("Web Tools")


@mcp.tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> Dict[str, Any]:
    """Search the web using Tavily for current information and documentation.

    This tool searches the web and returns relevant results. After receiving results,
    synthesize the information into a natural, helpful response for the user.

    Args:
        query: The search query (be specific and detailed)
        max_results: Number of results to return (default: 5)
        topic: Search topic type - "general" for most queries, "news" for current events
        include_raw_content: Include full page content (warning: uses more tokens)

    Returns:
        Dictionary containing:
        - results: List of search results with title, url, content, and score
        - query: The original search query
    """
    if tavily_client is None:
        return {
            "error": "Tavily API key not configured. Set TAVILY_API_KEY environment variable or install tavily-python package.",
            "query": query,
        }

    try:
        search_docs = tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
        return search_docs
    except Exception as e:
        return {"error": f"Web search error: {str(e)}", "query": query}


@mcp.tool
def fetch_url(url: str, timeout: int = 30) -> Dict[str, Any]:
    """Fetch content from a URL and convert HTML to markdown format.

    This tool fetches web page content and converts it to clean markdown text,
    making it easy to read and process HTML content.

    Args:
        url: The URL to fetch (must be a valid HTTP/HTTPS URL)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Dictionary containing:
        - url: The final URL after redirects
        - markdown_content: The page content converted to markdown
        - status_code: HTTP status code
        - content_length: Length of the markdown content in characters
    """
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DeepAgents-Playbooks/1.0)"
            },
        )
        response.raise_for_status()

        # Convert HTML to markdown
        markdown_content = markdownify(response.text)

        return {
            "success": True,
            "url": str(response.url),
            "markdown_content": markdown_content,
            "status_code": response.status_code,
            "content_length": len(markdown_content),
        }
    except Exception as e:
        return {"success": False, "error": f"Fetch URL error: {str(e)}", "url": url}


@mcp.tool
def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    data: Optional[str] = None,
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make HTTP requests to APIs and web services.

    Args:
        url: Target URL
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: HTTP headers to include
        data: Request body data as string
        json_data: Request body data as JSON dict
        params: URL query parameters
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response data including status, headers, and content
    """
    try:
        kwargs = {"url": url, "method": method.upper(), "timeout": timeout}

        if headers:
            kwargs["headers"] = headers
        if params:
            kwargs["params"] = params
        if json_data:
            kwargs["json"] = json_data
        elif data:
            kwargs["data"] = data

        response = requests.request(**kwargs)

        # Try to parse as JSON
        try:
            content = response.json()
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            content = response.text

        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": content,
            "url": response.url,
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": 0,
            "error": f"Request timed out after {timeout} seconds",
            "url": url,
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "status_code": 0,
            "error": f"Request error: {str(e)}",
            "url": url,
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": 0,
            "error": f"Error making request: {str(e)}",
            "url": url,
        }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
