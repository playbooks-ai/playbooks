import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from playbooks.cli import compile_playbook, run_application


class TestCLICompile:
    """Test the CLI compile functionality."""

    def test_compile_playbook_to_stdout(self, test_data_dir, capsys):
        """Test compiling a playbook and outputting to stdout."""
        playbook_path = test_data_dir / "01-hello-playbooks.pb"

        # Call the compile function directly
        compile_playbook(str(playbook_path))

        # Capture the output
        captured = capsys.readouterr()

        # Verify the compiled output contains expected elements
        assert "# HelloWorld" in captured.out
        assert "## HelloWorldDemo() -> None" in captured.out
        assert "01:QUE Greet the user" in captured.out
        assert "02:QUE Tell the user that this is a demo" in captured.out
        assert "03:QUE Say goodbye to the user" in captured.out
        assert "public.json" in captured.out

    def test_compile_playbook_to_file(self, test_data_dir):
        """Test compiling a playbook and saving to a file."""
        playbook_path = test_data_dir / "01-hello-playbooks.pb"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pbc", delete=False
        ) as tmp_file:
            output_path = tmp_file.name

        try:
            # Call the compile function with output file
            compile_playbook(str(playbook_path), output_path)

            # Verify the file was created and contains expected content
            assert Path(output_path).exists()

            with open(output_path, "r") as f:
                content = f.read()

            assert "# HelloWorld" in content
            assert "## HelloWorldDemo() -> None" in content
            assert "01:QUE Greet the user" in content
            assert "public.json" in content

        finally:
            # Clean up
            if Path(output_path).exists():
                Path(output_path).unlink()

    def test_compile_nonexistent_file(self):
        """Test compiling a non-existent file raises appropriate error."""
        with pytest.raises(SystemExit):
            compile_playbook("nonexistent.pb")


class TestCLIRun:
    """Test the CLI run functionality."""

    @pytest.mark.asyncio
    async def test_run_application_with_agent_chat(self, test_data_dir):
        """Test running a playbook with the agent_chat application."""
        playbook_path = test_data_dir / "01-hello-playbooks.pb"

        # This test will actually run the application but we'll interrupt it quickly
        # since it's an interactive application
        task = asyncio.create_task(
            run_application("playbooks.applications.agent_chat", [str(playbook_path)])
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

    def test_cli_compile_stdout(self, test_data_dir):
        """Test CLI compile command outputting to stdout."""
        playbook_path = test_data_dir / "01-hello-playbooks.pb"
        project_root = Path(__file__).parent.parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "compile", str(playbook_path)],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 0
        assert "# HelloWorld" in result.stdout
        assert "## HelloWorldDemo() -> None" in result.stdout
        assert "01:QUE Greet the user" in result.stdout

    def test_cli_compile_to_file(self, test_data_dir):
        """Test CLI compile command saving to file."""
        playbook_path = test_data_dir / "01-hello-playbooks.pb"
        project_root = Path(__file__).parent.parent.parent.parent

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".pbc", delete=False
        ) as tmp_file:
            output_path = tmp_file.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "playbooks",
                    "compile",
                    str(playbook_path),
                    "--output",
                    output_path,
                ],
                capture_output=True,
                text=True,
                cwd=project_root,
            )

            assert result.returncode == 0
            assert "Compiled playbook saved to:" in result.stdout

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
        assert "Playbook file not found" in result.stdout

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
        assert "Playbook file not found" in result.stdout

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
        # Filter out files that are known to not meet the H1/H2 requirements
        valid_pb_files = [f for f in pb_files if f.name not in ["markdown.pb"]]
        assert len(valid_pb_files) > 0, "No valid .pb files found in test data"

        for pb_file in valid_pb_files:
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
        playbook_path = test_data_dir / "01-hello-playbooks.pb"
        project_root = Path(__file__).parent.parent.parent.parent

        # Start the process
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(playbook_path),
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
