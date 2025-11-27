import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestCLIIntegration:
    """Integration tests that invoke the CLI as a subprocess."""

    def test_cli_help(self):
        """Test that the CLI help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent.parent,  # Go to project root
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
            cwd=Path(__file__).parent.parent.parent,  # Go to project root
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
            cwd=Path(__file__).parent.parent.parent,
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
            cwd=Path(__file__).parent.parent.parent,
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
        project_root = Path(__file__).parent.parent.parent

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
        project_root = Path(__file__).parent.parent.parent

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
            assert "Compiled Playbooks program saved to:" in result.stderr

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
        project_root = Path(__file__).parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "compile", "nonexistent.pb"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_cli_run_nonexistent_file(self):
        """Test CLI run with non-existent file."""
        project_root = Path(__file__).parent.parent.parent

        result = subprocess.run(
            [sys.executable, "-m", "playbooks", "run", "nonexistent.pb"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        assert result.returncode == 1
        assert "not found" in result.stderr

    def test_cli_no_command(self):
        """Test CLI with no command shows help."""
        project_root = Path(__file__).parent.parent.parent

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
        project_root = Path(__file__).parent.parent.parent

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
        project_root = Path(__file__).parent.parent.parent

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
