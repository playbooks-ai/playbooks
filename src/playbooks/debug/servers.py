"""
Debug server management for Playbooks.

This module manages debug server connections following the debugpy pattern.
"""

import socket
import threading
from typing import Optional, Tuple

from ..common import log, sockets

# Global server state
_server_socket: Optional[socket.socket] = None
_server_thread: Optional[threading.Thread] = None
_server_lock = threading.Lock()
_disconnected_event = threading.Event()


def serve(host: str, port: int = 0) -> Tuple[str, int]:
    """Start serving debug server connections."""
    log.info(f"Debug server would listen on {host}:{port}")
    return host, port or 7529


def stop_serving():
    """Stop serving debug server connections."""
    log.info("Stopping debug server")
    _disconnected_event.set()


def wait_until_disconnected():
    """Wait until the debug server is disconnected."""
    _disconnected_event.wait()


def _server_worker():
    """Worker thread for handling server connections."""
    global _server_socket

    try:
        while _server_socket:
            try:
                client_socket, client_address = _server_socket.accept()
                log.info(f"Debug server accepted connection from {client_address}")

                # Handle client in a separate thread
                client_thread = threading.Thread(
                    target=_handle_client,
                    args=(client_socket, client_address),
                    name=f"PlaybooksDebugClient-{client_address}",
                    daemon=True,
                )
                client_thread.start()

            except OSError:
                # Socket was closed
                break
            except Exception as e:
                log.error(f"Error accepting client connection: {e}")

    except Exception as e:
        log.error(f"Debug server worker error: {e}")
    finally:
        log.info("Debug server worker thread ended")


def _handle_client(client_socket: socket.socket, client_address):
    """Handle a client connection."""
    try:
        # For now, just close the connection
        # In a full implementation, this would handle the DAP protocol
        log.info(f"Handling client {client_address}")

        # TODO: Implement DAP protocol handling here
        # This would involve reading DAP messages and responding appropriately

    except Exception as e:
        log.error(f"Error handling client {client_address}: {e}")
    finally:
        sockets.close_socket(client_socket)
        log.info(f"Client {client_address} disconnected")
