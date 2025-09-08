import asyncio
import json
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from playbooks.cli import compile, run_application
from playbooks.exceptions import ProgramLoadError


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

        # Start the application with debug enabled and wait-for-client
        task = asyncio.create_task(
            run_application(
                "playbooks.applications.agent_chat",
                [str(playbooks_path)],
                enable_debug=True,
                debug_port=debug_port,
                debug_host="127.0.0.1",
                wait_for_client=True,
                stop_on_entry=True,
            )
        )

        try:
            # Give the debug server more time to start
            await asyncio.sleep(2.0)

            # Try to connect to the debug server to verify it's running
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", debug_port), timeout=5.0
            )

            # Wait a bit for the debug server to be ready
            await asyncio.sleep(0.5)

            # Send a continue command to let the playbook proceed
            continue_command = {"command": "continue"}
            writer.write((json.dumps(continue_command) + "\n").encode())
            await writer.drain()

            # Since 01-hello-playbooks.pb is non-interactive, it should complete quickly
            # We'll wait a bit for it to process and then check if it's done
            await asyncio.sleep(2.0)

            # For a non-interactive playbook, the task might complete on its own
            if task.done():
                # Task completed successfully
                await task  # This will raise any exceptions that occurred
                assert True
            else:
                # If it's still running after the continue command, that's also OK
                # as it means the debug server started successfully
                assert True

            # Close the connection
            writer.close()
            await writer.wait_closed()

        except (asyncio.TimeoutError, ConnectionRefusedError) as e:
            # Debug server is not running or not accessible
            pytest.fail(f"Debug server was not started or is not accessible: {e}")
        except Exception as e:
            # Other unexpected errors
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


class TestCLIIntegration:
    """Integration tests that invoke the CLI as a subprocess."""

    def test_cli_help(self):
        """Test that the CLI help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,  # Go to project root
        )

        assert result.returncode == 0
        assert "Playbooks CLI" in result.stdout
        assert "run" in result.stdout
        assert "compile" in result.stdout

    def test_cli_version(self):
        """Test that the CLI version command works."""
        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "--version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,  # Go to project root
        )

        assert result.returncode == 0
        assert "playbooks" in result.stdout
        # Check that it contains a version number (format: x.y.z)
        import re

        version_pattern = r"playbooks \d+\.\d+\.\d+"
        assert re.search(
            version_pattern, result.stdout
        ), f"Version output doesn't match expected pattern: {result.stdout}"

    def test_cli_compile_help(self):
        """Test that the CLI compile help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "compile", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,
        )

        assert result.returncode == 0
        assert "compile" in result.stdout
        assert "--output" in result.stdout

    def test_cli_run_help(self):
        """Test that the CLI run help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "run", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent.parent,
        )

        assert result.returncode == 0
        assert "run" in result.stdout
        assert "--application" in result.stdout
        # Check that all debug options are present in help
        assert "--debug" in result.stdout
        assert "--debug-host" in result.stdout
        assert "--debug-port" in result.stdout
        assert "--wait-for-client" in result.stdout
        assert "--stop-on-entry" in result.stdout
        assert "-v" in result.stdout or "--verbose" in result.stdout

    def test_cli_compile_stdout(self, test_data_dir):
        """Test CLI compile command outputting to stdout."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"
        project_root = Path(__file__).parent.parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "compile", str(playbooks_path)],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 0
        assert "# HelloWorld" in result.stdout
        assert "## HelloWorldDemo() -> None" in result.stdout
        assert "- 01:QUE Say(" in result.stdout

    def test_cli_compile_to_file(self, test_data_dir):
        """Test CLI compile command saving to file."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"
        project_root = Path(__file__).parent.parent.parent.parent

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pbasm", delete=False
        ) as tmp_file:
            output_path = tmp_file.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "playbooks",
                    "compile",
                    str(playbooks_path),
                    "--output",
                    output_path,
                ],
                capture_output=True,
                text=True,
                cwd=project_root,
            )

            assert result.returncode == 0
            assert "Compiled Playbooks program saved to:" in result.stdout

            # Verify the file was created and contains expected content
            assert Path(output_path).exists()

            with open(output_path, "r") as f:
                content = f.read()

            assert "# HelloWorld" in content
            assert "## HelloWorldDemo() -> None" in content

        finally:
            # Clean up
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_cli_compile_nonexistent_file(self):
        """Test CLI compile with non-existent file."""
        project_root = Path(__file__).parent.parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "compile", "nonexistent.pb"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 1
        assert "not found" in result.stdout

    def test_cli_run_nonexistent_file(self):
        """Test CLI run with non-existent file."""
        project_root = Path(__file__).parent.parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "run", "nonexistent.pb"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 1
        assert "not found" in result.stdout

    def test_cli_no_command(self):
        """Test CLI with no command shows help."""
        project_root = Path(__file__).parent.parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 1
        assert "Playbooks CLI" in result.stdout


class TestCLIWithExamples:
    """Test CLI with various example playbooks."""

    def test_compile_all_examples(self, test_data_dir):
        """Test compiling all example playbooks."""
        project_root = Path(__file__).parent.parent.parent.parent

        # Find all .pb files in test data, but exclude ones that don't meet format requirements
        pb_files = list(test_data_dir.glob("*.pb"))
        assert len(pb_files) > 0, "No valid .pb files found in test data"

        for pb_file in pb_files:
            # if file name starts with two digits, compile it
            if re.match(r"^\d{2}-", pb_file.name):
                result = subprocess.run(
                    [sys.executable, "-m", "playbooks", "compile", str(pb_file)],
                    capture_output=True,
                    text=True,
                    cwd=project_root,
                )

                # All files should compile successfully
                assert (
                    result.returncode == 0
                ), f"Failed to compile {pb_file.name}: {result.stdout}"
                assert len(result.stdout) > 0, f"No output for {pb_file.name}"

    @pytest.mark.parametrize(
        "application",
        [
            "playbooks.applications.agent_chat",
            # Only test agent_chat since the others may have additional dependencies
        ],
    )
    def test_run_with_different_applications(self, test_data_dir, application):
        """Test running playbooks with different applications."""
        playbooks_path = test_data_dir / "01-hello-playbooks.pb"
        project_root = Path(__file__).parent.parent.parent.parent

        # Start the process
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(playbooks_path),
                "--application",
                application,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=project_root,
        )

        try:
            # Let it run briefly to ensure it starts up
            stdout, stderr = process.communicate(timeout=2)

            # If it times out, that's actually good - it means the app started
            # and is waiting for input (which is expected behavior)

        except subprocess.TimeoutExpired:
            # This is expected for interactive applications
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

            # The fact that it didn't exit immediately means it started successfully
            assert True
        else:
            # If it exited immediately, check if it was due to an error
            if process.returncode != 0:
                pytest.fail(f"Application {application} failed to start: {stderr}")
