"""
Web Search Chat Agent implemented using LangGraph.
This agent can engage in conversation and perform web searches to gather information.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolExecutor
from tavily import TavilyClient

# Type definitions
AgentState = TypedDict(
    "AgentState",
    {
        "messages": List[BaseMessage],
        "should_search": bool,
        "search_queries": List[str],
        "search_results": List[Dict[str, Any]],
        "is_nsfw": bool,
    },
)

# Initialize tools
tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))


def search_web(query: str) -> Dict[str, Any]:
    """Search the web using Tavily API."""
    return tavily_client.search(query, limit=1)


tools = [search_web]
tool_executor = ToolExecutor(tools)

# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4-turbo-preview",
    temperature=0.7,
)

# Prompts
AGENT_SYSTEM_PROMPT = """You are a knowledgeable and friendly AI assistant who can search the internet to provide accurate and helpful information."""

analyze_input_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            'Analyze if the user\'s query:\n1. Requires web search to provide accurate information\n2. Contains NSFW content\n\nRespond in JSON format:\n{\n  "needs_search": boolean,\n  "is_nsfw": boolean\n}',
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

search_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Generate 1-3 specific search queries to gather information needed to help the user.",
        ),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "List each query on a new line, no other text."),
    ]
)

response_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", AGENT_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
        (
            "human",
            "Search results if any: {search_results}\n\nProvide a natural, conversational response.",
        ),
    ]
)


def analyze_input(state: AgentState) -> AgentState:
    """Analyze user input to determine if web search is needed and if content is NSFW."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    response = llm.invoke(
        analyze_input_prompt.format(
            messages=state["messages"], current_time=current_time
        )
    )

    try:
        import json

        analysis = json.loads(response.content)
        state["should_search"] = analysis["needs_search"]
        state["is_nsfw"] = analysis["is_nsfw"]
    except json.JSONDecodeError:
        state["should_search"] = False
        state["is_nsfw"] = False

    return state


def generate_search_queries(state: AgentState) -> AgentState:
    """Generate search queries based on the conversation."""
    if not state["should_search"]:
        return state

    response = llm.invoke(search_prompt.format(messages=state["messages"]))

    state["search_queries"] = [
        query.strip() for query in response.content.split("\n") if query.strip()
    ]
    return state


def execute_searches(state: AgentState) -> AgentState:
    """Execute web searches for all queries."""
    if not state["should_search"]:
        return state

    search_results = []
    for query in state["search_queries"]:
        try:
            result = tool_executor.execute("search_web", query)
            search_results.append(result)
        except Exception as e:
            search_results.append({"error": str(e), "query": query})

    state["search_results"] = search_results
    return state


def generate_response(state: AgentState) -> AgentState:
    """Generate a response based on the conversation and search results."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if state["is_nsfw"]:
        state["messages"].append(
            AIMessage(
                content="I apologize, but I cannot assist with NSFW content. "
                "Please feel free to ask me about something else!"
            )
        )
        return state

    response = llm.invoke(
        response_prompt.format(
            messages=state["messages"],
            search_results=state["search_results"] if state["should_search"] else [],
            current_time=current_time,
        )
    )

    state["messages"].append(AIMessage(content=response.content))
    state["search_queries"] = []
    state["search_results"] = []
    state["should_search"] = False
    state["is_nsfw"] = False
    return state


# Create the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("analyze_input", analyze_input)
workflow.add_node("generate_search_queries", generate_search_queries)
workflow.add_node("execute_searches", execute_searches)
workflow.add_node("generate_response", generate_response)

# Add edges
workflow.add_edge("analyze_input", "generate_search_queries")
workflow.add_edge("generate_search_queries", "execute_searches")
workflow.add_edge("execute_searches", "generate_response")

# Set entry point
workflow.set_entry_point("analyze_input")

# Compile the graph
app = workflow.compile()


def chat() -> None:
    """Run the chat application."""
    # Initialize the state
    state = {
        "messages": [
            AIMessage(
                content=generate_response(
                    {
                        "messages": [],
                        "should_search": False,
                        "search_queries": [],
                        "search_results": [],
                        "is_nsfw": False,
                    }
                )["messages"][-1].content
            )
        ],
        "should_search": False,
        "search_queries": [],
        "search_results": [],
        "is_nsfw": False,
    }

    print("Assistant: " + state["messages"][0].content)

    while True:
        # Get user input
        user_input = input("You: ").strip()
        if user_input.lower() in ["quit", "exit", "bye"]:
            print("Assistant: Goodbye! Have a great day!")
            break

        # Add user message to state
        state["messages"].append(HumanMessage(content=user_input))

        # Run the graph
        for new_state in app.stream(state):
            state = new_state
            if len(state["messages"]) > 0 and isinstance(
                state["messages"][-1], AIMessage
            ):
                print("Assistant:", state["messages"][-1].content)


if __name__ == "__main__":
    chat()
