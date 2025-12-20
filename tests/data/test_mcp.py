"""Test MCP server file for memory:// transport testing."""

import json

from fastmcp import FastMCP

# This 'mcp' variable is what the memory:// protocol looks for by default
mcp = FastMCP("Test Server")

# Data store for stateful operations
_data_store = {
    "users": {
        "1": {"id": "1", "name": "Alice", "email": "alice@example.com", "active": True},
        "2": {"id": "2", "name": "Bob", "email": "bob@example.com", "active": False},
        "3": {
            "id": "3",
            "name": "Charlie",
            "email": "charlie@example.com",
            "active": True,
        },
    },
    "tasks": [],
    "counter": 0,
}


@mcp.tool()
async def get_secret() -> str:
    """Returns a secret message."""
    return "Playbooks+MCP FTW!"


@mcp.tool()
async def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@mcp.tool()
async def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers together."""
    return a * b


@mcp.tool()
async def greet(name: str, greeting: str = "Hello") -> str:
    """Greet someone with a custom greeting."""
    return f"{greeting}, {name}!"


@mcp.tool()
async def get_user_info(user_id: str) -> dict:
    """Get information about a user."""
    if user_id not in _data_store["users"]:
        raise ValueError(f"User with ID {user_id} not found")
    return _data_store["users"][user_id]


@mcp.tool()
async def list_users(active_only: bool = False) -> list:
    """List all users or only active users."""
    users = list(_data_store["users"].values())
    if active_only:
        users = [user for user in users if user["active"]]
    return users


@mcp.tool()
async def create_task(
    title: str, description: str = "", priority: str = "medium"
) -> dict:
    """Create a new task."""
    task_id = len(_data_store["tasks"]) + 1
    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "completed": False,
    }
    _data_store["tasks"].append(task)
    return task


@mcp.tool()
async def list_tasks(completed: bool = None) -> list:
    """List tasks, optionally filtered by completion status."""
    tasks = _data_store["tasks"]
    if completed is not None:
        tasks = [task for task in tasks if task["completed"] == completed]
    return tasks


@mcp.tool()
async def increment_counter() -> int:
    """Increment the server counter and return the new value."""
    _data_store["counter"] += 1
    return _data_store["counter"]


@mcp.tool()
async def get_counter() -> int:
    """Get the current counter value."""
    return _data_store["counter"]


@mcp.tool()
async def reset_counter() -> int:
    """Reset the counter to zero."""
    _data_store["counter"] = 0
    return _data_store["counter"]


@mcp.tool()
async def simulate_error(error_type: str = "generic") -> str:
    """Simulate various types of errors for testing error handling."""
    if error_type == "timeout":
        raise TimeoutError("Simulated timeout error")
    elif error_type == "auth":
        raise PermissionError("Simulated authentication error")
    elif error_type == "not_found":
        raise FileNotFoundError("Simulated resource not found error")
    elif error_type == "value":
        raise ValueError("Simulated value error")
    else:
        raise RuntimeError("Simulated generic error")


# Resources
@mcp.resource("config://version")
def get_version() -> str:
    """Get the server version."""
    return "1.0.0"


@mcp.resource("data://users")
def get_all_users() -> str:
    """Get all users as JSON."""
    return json.dumps(list(_data_store["users"].values()))


@mcp.resource("data://user/{user_id}")
def get_user_resource(user_id: str) -> str:
    """Get a specific user as JSON resource."""
    if user_id not in _data_store["users"]:
        raise FileNotFoundError(f"User {user_id} not found")
    return json.dumps(_data_store["users"][user_id])


@mcp.resource("data://stats")
def get_stats() -> str:
    """Get server statistics."""
    return json.dumps(
        {
            "total_users": len(_data_store["users"]),
            "active_users": len(
                [u for u in _data_store["users"].values() if u["active"]]
            ),
            "total_tasks": len(_data_store["tasks"]),
            "completed_tasks": len([t for t in _data_store["tasks"] if t["completed"]]),
            "counter_value": _data_store["counter"],
        }
    )


# Prompts
@mcp.prompt()
def greeting_prompt(name: str, style: str = "formal") -> str:
    """Generate a greeting prompt.

    Args:
        name: Name of the person to greet
        style: Style of greeting (formal, casual, friendly)

    Returns:
        Greeting prompt text
    """
    if style == "formal":
        return f"Good day, {name}. I hope you are well."
    elif style == "casual":
        return f"Hey {name}, what's up?"
    elif style == "friendly":
        return f"Hi there {name}! Great to see you!"
    else:
        return f"Hello {name}!"


@mcp.prompt()
def task_summary_prompt(user_id: str) -> str:
    """Generate a task summary prompt for a user.

    Args:
        user_id: ID of the user

    Returns:
        Task summary prompt
    """
    user = _data_store["users"].get(user_id, {"name": "Unknown"})
    user_tasks = [t for t in _data_store["tasks"] if t.get("assigned_to") == user_id]

    return f"""
Task Summary for {user["name"]}:

You have {len(user_tasks)} tasks assigned to you.
Please review your tasks and prioritize them accordingly.

Remember to:
1. Focus on high-priority tasks first
2. Update task status as you progress
3. Ask for help if you're blocked

Have a productive day!
"""


@mcp.prompt()
def code_review_prompt(language: str = "python", complexity: str = "medium") -> str:
    """Generate a code review prompt.

    Args:
        language: Programming language
        complexity: Code complexity level

    Returns:
        Code review prompt
    """
    return f"""
Code Review Guidelines for {language.title()}:

Complexity Level: {complexity.title()}

Please review the code for:
1. Correctness and logic
2. Code style and formatting
3. Performance considerations
4. Security implications
5. Documentation and comments

{"Focus on advanced patterns and optimization." if complexity == "high" else "Focus on clarity and best practices."}

Provide constructive feedback and suggestions for improvement.
"""
