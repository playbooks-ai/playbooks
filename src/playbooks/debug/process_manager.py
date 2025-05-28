"""Process manager for Playbooks debugging."""

from ..common import log


class ProcessManager:
    """Manages debugged processes."""

    def __init__(self):
        self.logger = log
        self.processes = {}

    def start_process(self, process_id, command):
        """Start a new process."""
        self.logger.info(f"Starting process {process_id}: {command}")

    def stop_process(self, process_id):
        """Stop a process."""
        self.logger.info(f"Stopping process {process_id}")

    def get_process(self, process_id):
        """Get a process by ID."""
        return self.processes.get(process_id)
