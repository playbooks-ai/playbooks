import asyncio
import json
import socket
import tempfile
from pathlib import Path

import pytest

from playbooks.cli import compile, run_application
from playbooks.core.exceptions import ProgramLoadError


class TestCLICompile:
    """Test the CLI compile functionality."""

    def test_compile_to_stdout(self, test_data_dir, capsys):
        """Test compiling a playbook and outputting to stdout."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"

        # Call the compile function directly
        compile([str(playbooks_path)])

        # Capture the output
        captured = capsys.readouterr()

        # Verify the compiled output contains expected elements
        assert "# HelloWorld" in captured.out
        assert "## HelloWorldDemo() -> None" in captured.out
        assert "- 01:QUE Say(" in captured.out
        assert "YLD for exit" in captured.out
        assert "public.json" in captured.out

    def test_compile_to_file(self, test_data_dir):
        """Test compiling a playbook and saving to a file."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pbasm", delete=False
        ) as tmp_file:
            output_path = tmp_file.name

        try:
            # Call the compile function with output file
            compile([str(playbooks_path)], output_path)

            # Verify the file was created and contains expected content
            assert Path(output_path).exists()

            with open(output_path, "r") as f:
                content = f.read()

            assert "# HelloWorld" in content
            assert "## HelloWorldDemo() -> None" in content
            assert "- 01:QUE Say(" in content
            assert "public.json" in content

        finally:
            # Clean up
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_compile_nonexistent_file(self):
        """Test compiling a non-existent file raises appropriate error."""
        with pytest.raises(ProgramLoadError):
            compile("nonexistent.pb")


class TestCLIRun:
    """Test the CLI run functionality."""

    @pytest.mark.asyncio
    async def test_run_application_with_agent_chat(self, test_data_dir):
        """Test running a playbook with the agent_chat application."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"

        # This test will actually run the application but we'll interrupt it quickly
        # since it's an interactive application
        task = asyncio.create_task(
            run_application("playbooks.applications.agent_chat", [str(playbooks_path)])
        )

        # Let it start up briefly
        await asyncio.sleep(0.1)

        # Cancel the task since it's interactive
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected for interactive applications

    @pytest.mark.asyncio
    async def test_run_application_with_debug_server(self, test_data_dir):
        """Test that the --debug flag starts a debug server and can accept connections."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"

        # Find an available port for testing
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            debug_port = s.getsockname()[1]

        # Start the application with debug enabled but WITHOUT wait_for_client
        # The debug server will attempt to accept a connection but will timeout after 15 seconds
        task = asyncio.create_task(
            run_application(
                "playbooks.applications.agent_chat",
                [str(playbooks_path)],
                enable_debug=True,
                debug_port=debug_port,
                debug_host="127.0.0.1",
                wait_for_client=False,
                stop_on_entry=False,
            )
        )

        try:
            # Give the debug server time to start (should be quick)
            await asyncio.sleep(1.0)

            # Try to connect to the debug server to verify it's running
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", debug_port), timeout=5.0
                )

                # Wait a bit for the debug server to process the connection
                await asyncio.sleep(0.2)

                # Send a simple get_threads command to verify the server responds
                get_threads_command = {"seq": 1, "command": "get_threads"}
                writer.write((json.dumps(get_threads_command) + "\n").encode())
                await writer.drain()

                # Give the server a moment to respond and then close
                await asyncio.sleep(0.1)

                # Close the connection
                writer.close()
                await writer.wait_closed()

                # If we got here, the debug server is running and accepting connections
                assert True

            except (asyncio.TimeoutError, ConnectionRefusedError) as e:
                pytest.fail(f"Debug server was not started or is not accessible: {e}")

            # Give the application time to complete its execution
            await asyncio.sleep(2.0)

        except Exception as e:
            pytest.fail(f"Unexpected error during test: {e}")
        finally:
            # Clean up the task if it's still running
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_run_application_invalid_module(self):
        """Test running with an invalid application module."""
        with pytest.raises(SystemExit):
            await run_application("nonexistent.module", ["test.pb"])

    @pytest.mark.asyncio
    async def test_run_application_module_without_main(self):
        """Test running with a module that doesn't have a main function."""
        with pytest.raises(SystemExit):
            await run_application("os", ["test.pb"])  # os module doesn't have main()
