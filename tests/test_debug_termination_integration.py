#!/usr/bin/env python3
"""
Integration test script for debug termination behavior.

This script runs a real playbooks program with debug server and verifies
that termination events are properly sent and the process exits cleanly.
"""
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_debug_termination():
    """Test complete debug termination flow."""
    print("🧪 Testing debug termination integration...")

    # Use existing test playbook that we know works
    test_file = Path(__file__).parent / "data" / "01-hello-playbooks.pb"
    if not test_file.exists():
        pytest.skip(f"Test playbook not found: {test_file}")

    print(f"📄 Using test playbook: {test_file}")

    debug_port = 7532
    events_received = []

    try:
        print(f"📄 Created test playbook: {test_file}")

        # Start playbooks with debug server
        print(f"🚀 Starting playbooks debug server on port {debug_port}")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                str(test_file),
                "--debug",
                "--debug-host",
                "127.0.0.1",
                "--debug-port",
                str(debug_port),
                "--wait-for-client",  # This makes it wait for our test client
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for debug server to start and retry connection
        print("🔗 Waiting for debug server to start...")
        reader, writer = None, None
        for attempt in range(10):  # Try for up to 10 seconds
            try:
                await asyncio.sleep(1)
                reader, writer = await asyncio.open_connection("127.0.0.1", debug_port)
                print(f"✅ Connected to debug server on attempt {attempt + 1}")
                break
            except ConnectionRefusedError:
                print(f"⏳ Attempt {attempt + 1}/10: Server not ready yet...")
                if attempt == 9:
                    # Get process output for debugging
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                        print(f"Process stdout: {stdout}")
                        print(f"Process stderr: {stderr}")
                    except Exception:
                        pass
                    raise Exception(
                        "Could not connect to debug server after 10 attempts"
                    )

        if not reader or not writer:
            raise Exception("Failed to establish connection")

        try:
            # Read events until termination
            print("📡 Listening for debug events...")
            timeout_count = 0
            while timeout_count < 3:  # Allow up to 3 timeouts
                try:
                    data = await asyncio.wait_for(reader.readline(), timeout=5)
                    if not data:
                        print("📡 Connection closed by server")
                        break

                    event_line = data.decode().strip()
                    if event_line:
                        try:
                            event = json.loads(event_line)
                            events_received.append(event)
                            event_type = event.get("type", "unknown")
                            print(f"📨 Received event: {event_type}")

                            if event_type == "program_terminated":
                                print("✅ Program termination event received!")
                                break
                            elif event_type == "disconnect":
                                print("🔌 Disconnect event received!")
                                break
                        except json.JSONDecodeError:
                            print(f"⚠️ Could not parse event: {event_line}")
                    else:
                        print("📡 Received empty line")

                except asyncio.TimeoutError:
                    timeout_count += 1
                    print(f"⏰ Timeout {timeout_count}/3 waiting for events")

                    # Check if process is still running
                    if process.poll() is not None:
                        print(f"🏁 Process has exited with code: {process.returncode}")
                        break

        finally:
            writer.close()
            await writer.wait_closed()

        # Wait for process to complete
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        # Verify results
        print("\n📊 Test Results:")
        print(f"Process exit code: {process.returncode}")
        print(f"Events received: {len(events_received)}")

        # Check for required events
        program_terminated = any(
            e.get("type") == "program_terminated" for e in events_received
        )
        disconnect_event = any(e.get("type") == "disconnect" for e in events_received)

        success = True

        if process.returncode != 0:
            print("❌ Process did not exit cleanly")
            print(f"STDERR: {stderr}")
            success = False

        if not program_terminated:
            print("❌ Did not receive program_terminated event")
            success = False
        else:
            print("✅ Received program_terminated event")

        if not disconnect_event:
            print("⚠️ Did not receive disconnect event (optional)")
        else:
            print("✅ Received disconnect event")

        if len(events_received) == 0:
            print("❌ No events received at all")
            success = False

        # Print event summary
        event_types = [e.get("type", "unknown") for e in events_received]
        print(f"Event types received: {set(event_types)}")

        return success

    finally:
        # Cleanup process
        if "process" in locals() and process.poll() is None:
            process.terminate()


@pytest.mark.asyncio
async def test_client_disconnect_handling():
    """Test that debug server handles client disconnection gracefully."""
    print("\n🧪 Testing client disconnect handling...")

    # Create minimal test playbook
    test_content = """# Client Disconnect Test
## TestAgent
### Trigger
When starting
### Steps
- Wait for user input
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".pb", delete=False) as f:
        f.write(test_content)
        test_file = f.name

    debug_port = 7533

    try:
        print(f"📄 Created test playbook: {test_file}")

        # Start playbooks with debug server
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "playbooks",
                "run",
                test_file,
                "--debug",
                "--debug-host",
                "127.0.0.1",
                "--debug-port",
                str(debug_port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for debug server to start
        await asyncio.sleep(2)

        # Connect and immediately disconnect multiple times
        for i in range(3):
            print(f"🔗 Connection attempt {i+1}")
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", debug_port)
                # Read one event then disconnect
                await asyncio.wait_for(reader.readline(), timeout=2)
                writer.close()
                await writer.wait_closed()
                print(f"✅ Connection {i+1} successful")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ Connection {i+1} failed: {e}")
                return False

        print("✅ Client disconnect handling test passed")
        return True

    finally:
        # Cleanup
        Path(test_file).unlink(missing_ok=True)
        if "process" in locals():
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


async def main():
    """Run all debug termination tests."""
    print("🎯 Running Debug Termination Integration Tests\n")

    tests = [test_debug_termination, test_client_disconnect_handling]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            success = await test()
            if success:
                passed += 1
                print("✅ PASSED\n")
            else:
                print("❌ FAILED\n")
        except Exception as e:
            print(f"💥 ERROR: {e}\n")

    print(f"📈 Test Summary: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("💔 Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
