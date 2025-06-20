"""Streamlit web interface for Playbooks Agent Chat."""

import json
import sys
from typing import Dict, Optional

import requests
import streamlit as st

from playbooks.enums import LLMMessageRole
from playbooks.utils.llm_helper import make_uncached_llm_message

# Constants
SERVER_URL = "http://localhost:8000"  # Default web agent chat server URL


def is_running_in_streamlit() -> bool:
    """Check if the script is running in a Streamlit context."""
    return st.runtime.exists()


def check_server_connection() -> bool:
    """Check if the web agent chat server is running and accessible."""
    try:
        response = requests.get(f"{SERVER_URL}/runs/new")
        return (
            response.status_code != 404
        )  # Any response other than 404 means server is running
    except requests.exceptions.ConnectionError:
        return False


def show_server_error():
    """Display a user-friendly error message when server is not accessible."""
    st.error(
        """
    🔴 Unable to connect to the Playbooks Agent Chat server!
    
    Please make sure:
    1. The web agent chat server is running (python web_agent_chat.py)
    2. The server is running on http://localhost:8000
    3. You have a stable internet connection
    
    Once the server is running, refresh this page to try again.
    """
    )


def initialize_session_state():
    """Initialize session state variables."""
    if "run_id" not in st.session_state:
        st.session_state.run_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "playbook_path" not in st.session_state:
        st.session_state.playbook_path = "tests/data/01-hello-playbooks.pb"


def process_streaming_messages(messages):
    """Process streaming messages and return final text messages.

    When streaming messages are present, we show only the streaming content
    and ignore any traditional 'message' type entries to avoid duplication.
    """
    final_messages = []
    current_stream = ""
    current_agent = ""
    has_streaming = False

    # First pass: check if we have any streaming messages
    for msg in messages:
        if msg.get("type") in ["stream_start", "stream_update", "stream_complete"]:
            has_streaming = True
            break

    for msg in messages:
        msg_type = msg.get("type", "message")

        if msg_type == "stream_start":
            current_stream = ""
            current_agent = msg.get("agent", "Agent")

        elif msg_type == "stream_update":
            current_stream += msg.get("content", "")

        elif msg_type == "stream_complete":
            if current_stream:
                final_messages.append(
                    {"agent": current_agent, "content": current_stream}
                )
            current_stream = ""

        elif msg_type == "message":
            # Only process traditional messages when there's no streaming
            # This prevents duplication since Say() content is delivered via streaming
            if not has_streaming:
                final_messages.append(
                    {"agent": "Agent", "content": msg.get("content", "")}
                )

    return final_messages


def create_new_chat(playbook_path: str) -> Optional[str]:
    """Create a new chat session with the given playbook path."""
    if not check_server_connection():
        show_server_error()
        return None

    try:
        response = requests.post(
            f"{SERVER_URL}/runs/new",
            json={"path": playbook_path},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code == 200:
            data = response.json()
            # Process streaming messages and add to chat
            streaming_messages = data.get("messages", [])
            final_messages = process_streaming_messages(streaming_messages)

            for msg in final_messages:
                st.session_state.messages.append(
                    make_uncached_llm_message(
                        f"**{msg['agent']}:** {msg['content']}",
                        LLMMessageRole.ASSISTANT,
                    )
                )
            return data["run_id"]
        elif response.status_code == 400:
            st.error(f"Invalid playbook path: {response.text}")
            return None
        else:
            st.error(f"Server error: {response.text}")
            return None
    except requests.exceptions.RequestException:
        show_server_error()
        return None


def send_message(run_id: str, message: str) -> Dict:
    """Send a message to the chat session."""
    if not check_server_connection():
        show_server_error()
        return {"messages": [], "terminated": True}

    try:
        response = requests.post(
            f"{SERVER_URL}/runs/{run_id}/messages",
            json={"message": message},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            st.error("Chat session not found. Please start a new chat.")
            return {"messages": [], "terminated": True}
        else:
            st.error(f"Server error: {response.text}")
            return {"messages": [], "terminated": False}
    except requests.exceptions.RequestException:
        show_server_error()
        return {"messages": [], "terminated": True}


def display_chat_interface():
    """Display the main chat interface."""
    st.title("Playbooks Agent Chat")

    # Check server connection first
    if not check_server_connection():
        show_server_error()
        return

    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        playbook_path = st.text_input(
            "Playbook Path",
            value=st.session_state.playbook_path,
            help="Path to the playbook file",
        )

        if st.button("New Chat") and playbook_path:
            st.session_state.playbook_path = playbook_path
            # Clear old messages before creating new chat
            st.session_state.messages = []
            run_id = create_new_chat(playbook_path)
            if run_id:
                st.session_state.run_id = run_id
                st.rerun()

    # Main chat area
    if not st.session_state.run_id:
        st.info(
            """
        👋 Welcome to Playbooks Agent Chat!
        
        To get started:
        1. Enter the path to your playbook file in the sidebar
        2. Click 'New Chat' to begin a conversation
        3. Type your messages in the chat input below
        """
        )
        return

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat
        st.session_state.messages.append(
            make_uncached_llm_message(prompt, LLMMessageRole.USER)
        )
        with st.chat_message(LLMMessageRole.USER):
            st.write(prompt)

        # Real-time streaming display
        with st.chat_message(LLMMessageRole.ASSISTANT):
            # Create container for the message
            message_placeholder = st.empty()

            # Stream the response in real-time
            try:
                response = requests.post(
                    f"{SERVER_URL}/runs/{st.session_state.run_id}/stream",
                    json={"message": prompt},
                    headers={"Content-Type": "application/json"},
                    stream=True,
                )

                if response.status_code != 200:
                    error_msg = f"Error: Server returned {response.status_code}"
                    message_placeholder.markdown(error_msg)
                    st.session_state.messages.append(
                        make_uncached_llm_message(error_msg, LLMMessageRole.ASSISTANT)
                    )
                else:
                    # Real-time streaming
                    accumulated_content = ""
                    agent_name = "Agent"
                    first_stream = True

                    for line in response.iter_lines():
                        if not line:
                            continue

                        line = line.decode("utf-8")
                        if not line.startswith("data: "):
                            continue

                        try:
                            event_data = json.loads(line[6:])
                            event_type = event_data.get("type")

                            if event_type == "stream_start":
                                agent_name = event_data.get("agent", "Agent")
                                if not first_stream:
                                    accumulated_content += "\n\n"
                                first_stream = False

                            elif event_type == "stream_update":
                                content = event_data.get("content", "")
                                if content:
                                    accumulated_content += content
                                    # Update display in real-time with cursor
                                    current_display = (
                                        f"**{agent_name}:** {accumulated_content}▏"
                                    )
                                    message_placeholder.markdown(current_display)

                            elif event_type == "stream_complete":
                                content = event_data.get("content", "")
                                current_display = (
                                    f"**{agent_name}:** {accumulated_content}"
                                )
                                message_placeholder.markdown(current_display)
                                st.session_state.messages.append(
                                    make_uncached_llm_message(
                                        current_display, LLMMessageRole.ASSISTANT
                                    )
                                )

                            elif event_type == "done":
                                break

                            elif event_type == "error":
                                error_msg = (
                                    f"Error: {event_data.get('error', 'Unknown error')}"
                                )
                                message_placeholder.markdown(error_msg)
                                st.session_state.messages.append(
                                    make_uncached_llm_message(
                                        error_msg, LLMMessageRole.ASSISTANT
                                    )
                                )
                                break

                        except json.JSONDecodeError:
                            continue

                    # Final display without cursor
                    if accumulated_content:
                        final_message = f"**{agent_name}:** {accumulated_content}"
                        message_placeholder.markdown(final_message)
                        st.session_state.messages.append(
                            make_uncached_llm_message(
                                final_message, LLMMessageRole.ASSISTANT
                            )
                        )

            except Exception as e:
                error_msg = f"Error connecting to server: {str(e)}"
                message_placeholder.markdown(error_msg)
                st.session_state.messages.append(
                    make_uncached_llm_message(error_msg, LLMMessageRole.ASSISTANT)
                )

        response = {"terminated": False}  # Default response

        # Check if chat is terminated
        if response["terminated"]:
            st.info(
                """
            🏁 Chat session has ended.
            
            To start a new conversation:
            1. Enter a new playbook path in the sidebar
            2. Click 'New Chat'
            """
            )
            st.session_state.run_id = None


def print_error_and_exit():
    """Print a user-friendly error message and exit."""
    print(
        """
🚫 Error: This script must be run using Streamlit!

To run this application:

1. Make sure you have Streamlit installed:
   pip install streamlit

2. Run the application using:
   streamlit run src/playbooks/applications/streamlit_agent_chat.py

3. The application will open in your default web browser.

Note: Running this script directly with Python will not work properly.
    """
    )
    sys.exit(1)


def main():
    """Main function to run the Streamlit app."""
    try:
        st.set_page_config(
            page_title="Playbooks Agent Chat", page_icon="💬", layout="wide"
        )
        initialize_session_state()
        display_chat_interface()
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        raise e


if __name__ == "__main__":
    if not is_running_in_streamlit():
        print_error_and_exit()
    main()
