"""Debug client management for Playbooks."""

from typing import Tuple

from ..common import log


def serve(host: str, port: int = None) -> Tuple[str, int]:
    """Start serving debug client connections."""
    actual_port = port or 7529
    log.info(f"Debug client would listen on {host}:{actual_port}")
    return host, actual_port


def connect(host: str, port: int):
    """Connect to a debug server."""
    log.info(f"Debug client would connect to {host}:{port}")


def stop_serving():
    """Stop serving debug client connections."""
    log.info("Stopping debug client serving")
