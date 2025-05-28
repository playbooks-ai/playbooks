"""
Socket utilities for Playbooks debugging.

This module provides socket functionality following the debugpy pattern.
"""

import socket
from typing import Tuple


def get_default_localhost() -> str:
    """Get the default localhost address."""
    return "127.0.0.1"


def create_server(host: str, port: int, timeout: float = None) -> socket.socket:
    """Create a server socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if timeout is not None:
        sock.settimeout(timeout)

    sock.bind((host, port))
    sock.listen(5)
    return sock


def create_client(ipv6: bool = False) -> socket.socket:
    """Create a client socket."""
    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    return socket.socket(family, socket.SOCK_STREAM)


def get_address(sock: socket.socket) -> Tuple[str, int]:
    """Get the address of a socket."""
    return sock.getsockname()


def close_socket(sock: socket.socket):
    """Close a socket safely."""
    try:
        sock.close()
    except Exception:
        pass
