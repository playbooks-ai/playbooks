"""
Debug Adapter for Playbooks.

This module provides the main debug adapter that implements the Debug Adapter Protocol (DAP)
for Playbooks programs, following the pattern established by debugpy.
"""

import argparse
import atexit
import codecs
import os
import sys
from typing import Optional

from ..common import log
from . import clients, servers, sessions


class PlaybookDebugAdapter:
    """
    Main debug adapter for Playbooks that implements the Debug Adapter Protocol.

    This class follows the debugpy pattern for structuring debug adapters.
    """

    access_token: Optional[str] = None

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        is_server: bool = True,
        wait_for_client: bool = False,
        log_dir: Optional[str] = None,
        log_to_stderr: bool = False,
    ):
        self.host = host
        self.port = port
        self.is_server = is_server
        self.wait_for_client = wait_for_client
        self.log_dir = log_dir
        self.log_to_stderr = log_to_stderr

    def run(self):
        """Run the debug adapter."""
        # Set up logging
        if self.log_to_stderr:
            log.stderr.levels |= set(log.LEVELS)
        if self.log_dir is not None:
            log.log_dir = self.log_dir

        log.to_file(prefix="playbooks.adapter")
        log.describe_environment("Playbooks debug adapter startup environment:")

        # Generate access token
        if self.access_token is None:
            self.access_token = codecs.encode(os.urandom(32), "hex").decode("ascii")

        endpoints = {}

        try:
            if self.is_server:
                # Listen for client connections
                client_host, client_port = clients.serve(self.host, self.port)
                endpoints["client"] = {"host": client_host, "port": client_port}
                log.info(f"Listening for debug client on {client_host}:{client_port}")
            else:
                # Connect to existing server
                clients.connect(self.host, self.port)
                log.info(f"Connected to debug server at {self.host}:{self.port}")

        except Exception as exc:
            log.error(f"Failed to set up client connection: {exc}")
            sys.exit(1)

        # Set up cleanup
        atexit.register(servers.stop_serving)
        atexit.register(clients.stop_serving)

        if self.is_server:
            # Wait for connections and handle debug sessions
            servers.wait_until_disconnected()
            log.info(
                "All debug servers disconnected; waiting for remaining sessions..."
            )

            sessions.wait_until_ended()
            log.info("All debug sessions have ended; exiting.")


def main():
    """Main entry point for the debug adapter."""
    parser = argparse.ArgumentParser(
        description="Playbooks Debug Adapter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--listen",
        metavar="[HOST:]PORT",
        help="Listen for connections on the specified port (default host: 127.0.0.1)",
    )
    parser.add_argument(
        "--connect",
        metavar="HOST:PORT",
        help="Connect to a debug client at the specified host and port",
    )
    parser.add_argument(
        "--wait-for-client",
        action="store_true",
        help="Wait for a client to connect before starting execution",
    )
    parser.add_argument(
        "--log-to",
        metavar="PATH",
        help="Directory to write log files to",
    )
    parser.add_argument(
        "--log-to-stderr",
        action="store_true",
        help="Write logs to stderr",
    )

    args = parser.parse_args()

    # Parse connection details
    host = "127.0.0.1"
    port = None
    is_server = True

    if args.listen:
        if ":" in args.listen:
            host, port_str = args.listen.rsplit(":", 1)
            port = int(port_str)
        else:
            port = int(args.listen)
        is_server = True
    elif args.connect:
        if ":" in args.connect:
            host, port_str = args.connect.rsplit(":", 1)
            port = int(port_str)
        else:
            raise ValueError("--connect requires HOST:PORT format")
        is_server = False
    else:
        parser.error("Either --listen or --connect must be specified")

    # Create and run the adapter
    adapter = PlaybookDebugAdapter(
        host=host,
        port=port,
        is_server=is_server,
        wait_for_client=args.wait_for_client,
        log_dir=args.log_to,
        log_to_stderr=args.log_to_stderr,
    )

    adapter.run()


if __name__ == "__main__":
    main()
