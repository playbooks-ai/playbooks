"""Debug Adapter Protocol handler for Playbooks."""

from ..common import log


class DAPHandler:
    """Handles Debug Adapter Protocol messages."""

    def __init__(self):
        self.logger = log

    def handle_message(self, message):
        """Handle a DAP message."""
        self.logger.info(f"Handling DAP message: {message}")

    def send_response(self, response):
        """Send a DAP response."""
        self.logger.info(f"Sending DAP response: {response}")
