"""Streamlit web interface for Playbooks Agent Chat."""

import sys
from typing import Dict, Optional

import requests
import streamlit as st

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
        st.session_state.playbook_path = "tests/data/02-personalized-greeting.pb"


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
            # Add initial messages to the chat
            for message in data.get("messages", []):
                st.session_state.messages.append(
                    {"role": "assistant", "content": message}
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
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        # Send message to server and get response
        response = send_message(st.session_state.run_id, prompt)

        # Add agent messages to chat
        for message in response["messages"]:
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.write(message)

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


if __name__ == "__main__":
    if not is_running_in_streamlit():
        print_error_and_exit()
    main()
