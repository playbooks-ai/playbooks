"""Test MCP server for comprehensive testing of MCP agent functionality."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

# Set up logging for the test server
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestMCPServer:
    """Comprehensive test MCP server for testing MCP agent functionality."""

    def __init__(self):
        """Initialize the test MCP server."""
        self.mcp = FastMCP("Test MCP Server")
        self._setup_tools()
        self._setup_resources()
        self._setup_prompts()
        self._data_store = {
            "users": {
                "1": {
                    "id": "1",
                    "name": "Alice",
                    "email": "alice@example.com",
                    "active": True,
                },
                "2": {
                    "id": "2",
                    "name": "Bob",
                    "email": "bob@example.com",
                    "active": False,
                },
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

    def _setup_tools(self):
        """Set up various tools for testing."""

        @self.mcp.tool
        def add_numbers(a: int, b: int) -> int:
            """Add two numbers together.

            Args:
                a: First number
                b: Second number

            Returns:
                Sum of the two numbers
            """
            return a + b

        @self.mcp.tool
        def multiply_numbers(a: float, b: float) -> float:
            """Multiply two numbers together.

            Args:
                a: First number
                b: Second number

            Returns:
                Product of the two numbers
            """
            return a * b

        @self.mcp.tool
        def greet(name: str, greeting: str = "Hello") -> str:
            """Greet someone with a custom greeting.

            Args:
                name: Name of the person to greet
                greeting: Greeting to use (default: "Hello")

            Returns:
                Greeting message
            """
            return f"{greeting}, {name}!"

        @self.mcp.tool
        def get_user_info(user_id: str) -> Dict[str, Any]:
            """Get information about a user.

            Args:
                user_id: ID of the user to look up

            Returns:
                User information dictionary

            Raises:
                ValueError: If user not found
            """
            if user_id not in self._data_store["users"]:
                raise ValueError(f"User with ID {user_id} not found")
            return self._data_store["users"][user_id]

        @self.mcp.tool
        def list_users(active_only: bool = False) -> List[Dict[str, Any]]:
            """List all users or only active users.

            Args:
                active_only: If True, only return active users

            Returns:
                List of user dictionaries
            """
            users = list(self._data_store["users"].values())
            if active_only:
                users = [user for user in users if user["active"]]
            return users

        @self.mcp.tool
        def create_task(
            title: str, description: str = "", priority: str = "medium"
        ) -> Dict[str, Any]:
            """Create a new task.

            Args:
                title: Task title
                description: Task description (optional)
                priority: Task priority (low, medium, high)

            Returns:
                Created task dictionary
            """
            task_id = len(self._data_store["tasks"]) + 1
            task = {
                "id": task_id,
                "title": title,
                "description": description,
                "priority": priority,
                "completed": False,
            }
            self._data_store["tasks"].append(task)
            return task

        @self.mcp.tool
        def list_tasks(completed: Optional[bool] = None) -> List[Dict[str, Any]]:
            """List tasks, optionally filtered by completion status.

            Args:
                completed: If True, only completed tasks; if False, only incomplete; if None, all tasks

            Returns:
                List of task dictionaries
            """
            tasks = self._data_store["tasks"]
            if completed is not None:
                tasks = [task for task in tasks if task["completed"] == completed]
            return tasks

        @self.mcp.tool
        def increment_counter() -> int:
            """Increment the server counter and return the new value.

            Returns:
                New counter value
            """
            self._data_store["counter"] += 1
            return self._data_store["counter"]

        @self.mcp.tool
        def get_counter() -> int:
            """Get the current counter value.

            Returns:
                Current counter value
            """
            return self._data_store["counter"]

        @self.mcp.tool
        def reset_counter() -> int:
            """Reset the counter to zero.

            Returns:
                New counter value (0)
            """
            self._data_store["counter"] = 0
            return self._data_store["counter"]

        @self.mcp.tool
        def simulate_error(error_type: str = "generic") -> str:
            """Simulate various types of errors for testing error handling.

            Args:
                error_type: Type of error to simulate (generic, timeout, auth, not_found)

            Returns:
                Never returns, always raises an exception

            Raises:
                Various exceptions based on error_type
            """
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

        @self.mcp.tool
        def get_secret() -> str:
            """Get a secret message from the server.

            Returns:
                A secret message string
            """
            return "Playbooks+MCP FTW!"

    def _setup_resources(self):
        """Set up various resources for testing."""

        @self.mcp.resource("config://server_info")
        def get_server_info() -> str:
            """Get server information."""
            return json.dumps(
                {
                    "name": "Test MCP Server",
                    "version": "1.0.0",
                    "description": "Comprehensive test server for MCP agent testing",
                    "capabilities": ["tools", "resources", "prompts"],
                    "uptime": "test_mode",
                }
            )

        @self.mcp.resource("config://version")
        def get_version() -> str:
            """Get the server version."""
            return "1.0.0"

        @self.mcp.resource("data://users")
        def get_all_users() -> str:
            """Get all users as JSON."""
            return json.dumps(list(self._data_store["users"].values()))

        @self.mcp.resource("data://user/{user_id}")
        def get_user_resource(user_id: str) -> str:
            """Get a specific user as JSON resource."""
            if user_id not in self._data_store["users"]:
                raise FileNotFoundError(f"User {user_id} not found")
            return json.dumps(self._data_store["users"][user_id])

        @self.mcp.resource("data://tasks")
        def get_all_tasks() -> str:
            """Get all tasks as JSON."""
            return json.dumps(self._data_store["tasks"])

        @self.mcp.resource("data://stats")
        def get_stats() -> str:
            """Get server statistics."""
            return json.dumps(
                {
                    "total_users": len(self._data_store["users"]),
                    "active_users": len(
                        [u for u in self._data_store["users"].values() if u["active"]]
                    ),
                    "total_tasks": len(self._data_store["tasks"]),
                    "completed_tasks": len(
                        [t for t in self._data_store["tasks"] if t["completed"]]
                    ),
                    "counter_value": self._data_store["counter"],
                }
            )

        @self.mcp.resource("file://test.txt")
        def get_test_file() -> str:
            """Get a test file content."""
            return "This is a test file content for MCP resource testing."

        @self.mcp.resource("file://config.json")
        def get_config_file() -> str:
            """Get a configuration file."""
            return json.dumps(
                {
                    "debug": True,
                    "max_connections": 100,
                    "timeout": 30,
                    "features": ["auth", "logging", "metrics"],
                }
            )

    def _setup_prompts(self):
        """Set up various prompts for testing."""

        @self.mcp.prompt
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

        @self.mcp.prompt
        def task_summary_prompt(user_id: str) -> str:
            """Generate a task summary prompt for a user.

            Args:
                user_id: ID of the user

            Returns:
                Task summary prompt
            """
            user = self._data_store["users"].get(user_id, {"name": "Unknown"})
            user_tasks = [
                t for t in self._data_store["tasks"] if t.get("assigned_to") == user_id
            ]

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

        @self.mcp.prompt
        def code_review_prompt(
            language: str = "python", complexity: str = "medium"
        ) -> str:
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

    def get_server(self) -> FastMCP:
        """Get the FastMCP server instance."""
        return self.mcp

    def reset_data(self):
        """Reset the server data to initial state."""
        self._data_store = {
            "users": {
                "1": {
                    "id": "1",
                    "name": "Alice",
                    "email": "alice@example.com",
                    "active": True,
                },
                "2": {
                    "id": "2",
                    "name": "Bob",
                    "email": "bob@example.com",
                    "active": False,
                },
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


# Global test server instance
_test_server = None


def get_test_server() -> TestMCPServer:
    """Get the global test server instance."""
    global _test_server
    if _test_server is None:
        _test_server = TestMCPServer()
    return _test_server


# Example usage and testing
if __name__ == "__main__":

    async def test_server():
        """Test the MCP server functionality."""
        from fastmcp import Client

        server = get_test_server()
        mcp_server = server.get_server()

        async with Client(mcp_server) as client:
            # Test tools
            print("Testing tools...")
            result = await client.call_tool("add_numbers", {"a": 5, "b": 3})
            print(f"add_numbers(5, 3) = {result[0].text}")

            result = await client.call_tool(
                "greet", {"name": "World", "greeting": "Hi"}
            )
            print(f"greet result: {result[0].text}")

            # Test resources
            print("\nTesting resources...")
            resources = await client.list_resources()
            print(f"Available resources: {len(resources)}")

            result = await client.read_resource("config://version")
            print(f"Version: {result[0].text}")

            # Test prompts
            print("\nTesting prompts...")
            prompts = await client.list_prompts()
            print(f"Available prompts: {len(prompts)}")

            result = await client.get_prompt(
                "greeting_prompt", {"name": "Test", "style": "casual"}
            )
            print(f"Greeting prompt: {result.messages[0].content.text}")

    # Run the test
    asyncio.run(test_server())
