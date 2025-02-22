from typing import Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import Graph, StateGraph

from playbooks.config import LLMConfig
from playbooks.utils.llm_helper import get_completion


# Define the state type
class State(TypedDict):
    messages: Sequence[BaseMessage]
    next_step: str
    should_continue: bool


# Initialize LLM config
llm_config = LLMConfig(
    model="gpt-4", api_key=None
)  # API key will be loaded from environment


def is_nsfw(text: str) -> bool:
    messages = [
        {
            "role": "system",
            "content": "You are a content safety classifier. Respond with 'true' if the input contains NSFW (Not Safe For Work) content, or 'false' if it's safe. Only respond with 'true' or 'false', nothing else.",
        },
        {"role": "user", "content": text},
    ]
    response = get_completion(llm_config, messages)
    return response.choices[0].message.content.strip().lower() == "true"


def generate_response(messages: Sequence[BaseMessage]) -> str:
    # Convert messages to format expected by LLM
    formatted_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            formatted_messages.append({"role": "assistant", "content": msg.content})

    # Add system message
    formatted_messages.insert(
        0,
        {
            "role": "system",
            "content": "You are a friendly and helpful chat assistant. Keep responses concise and engaging. Maintain context of the conversation.",
        },
    )

    response = get_completion(llm_config, formatted_messages)
    return response.choices[0].message.content


# Define the chat functions
def greet(state: State) -> State:
    greeting_message = AIMessage(
        content="Hello! I'm your friendly chat assistant. How are you doing today?"
    )
    return {
        **state,
        "messages": [*state["messages"], greeting_message],
        "next_step": "process_user_input",
    }


def process_user_input(state: State) -> str:
    if not state["messages"]:
        return "respond"

    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage):
        if is_nsfw(last_message.content):
            return "handle_nsfw"
        if any(
            end in last_message.content.lower()
            for end in ["goodbye", "bye", "exit", "quit"]
        ):
            return "say_goodbye"
        return "respond"
    return "process_user_input"


def respond(state: State) -> State:
    response = AIMessage(content=generate_response(state["messages"]))
    return {
        **state,
        "messages": [*state["messages"], response],
        "next_step": "process_user_input",
    }


def handle_nsfw(state: State) -> State:
    messages = [
        {
            "role": "system",
            "content": "You are a content moderator. Generate a polite but firm response to redirect the conversation away from NSFW content. Keep it brief.",
        },
        {"role": "user", "content": "Generate a response to reject NSFW content"},
    ]
    response = get_completion(llm_config, messages)
    return {
        **state,
        "messages": [
            *state["messages"],
            AIMessage(content=response.choices[0].message.content),
        ],
        "next_step": "process_user_input",
    }


def say_goodbye(state: State) -> State:
    messages = [
        {
            "role": "system",
            "content": "Generate a friendly goodbye message to end the conversation.",
        },
        {"role": "user", "content": "Generate a goodbye message"},
    ]
    response = get_completion(llm_config, messages)
    return {
        **state,
        "messages": [
            *state["messages"],
            AIMessage(content=response.choices[0].message.content),
        ],
        "next_step": "end",
        "should_continue": False,
    }


# Create the graph
def create_chat_graph() -> Graph:
    workflow = StateGraph(State)

    # Add nodes
    workflow.add_node("greet", greet)
    workflow.add_node("process_user_input", process_user_input)
    workflow.add_node("respond", respond)
    workflow.add_node("handle_nsfw", handle_nsfw)
    workflow.add_node("say_goodbye", say_goodbye)

    # Add edges
    workflow.add_edge("greet", "process_user_input")
    workflow.add_edge("process_user_input", "respond")
    workflow.add_edge("process_user_input", "handle_nsfw")
    workflow.add_edge("process_user_input", "say_goodbye")
    workflow.add_edge("respond", "process_user_input")
    workflow.add_edge("handle_nsfw", "process_user_input")

    # Set entry point
    workflow.set_entry_point("greet")

    # Compile the graph
    return workflow.compile()


# Initialize and run the chat
def main():
    graph = create_chat_graph()
    config = {"messages": [], "next_step": "start", "should_continue": True}

    # Run the initial greeting
    result = graph.invoke(config)

    # Main chat loop
    while result["should_continue"]:
        # Get user input
        user_input = input("You: ")
        result["messages"].append(HumanMessage(content=user_input))

        # Process the input through the graph
        result = graph.invoke(result)

        # Display AI response
        if result["messages"]:
            last_message = result["messages"][-1]
            if isinstance(last_message, AIMessage):
                print(f"Assistant: {last_message.content}")


if __name__ == "__main__":
    main()
