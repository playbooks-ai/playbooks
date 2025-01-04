import pytest
import os
from playbooks.core.loader import load


@pytest.fixture(autouse=True)
def change_test_dir(request):
    # Get the directory containing the test file
    test_dir = os.path.dirname(__file__)
    # Get the playbooks package directory (2 levels up from test file)
    package_dir = os.path.abspath(os.path.join(test_dir, ".."))
    os.chdir(package_dir)


def test_load_single_file():
    content = load(["examples/playbooks/hello.md"])
    assert "# HelloWorld Agent" in content
    assert "## HelloWorld" in content
    assert "### Trigger" in content
    assert "### Steps" in content


def test_load_multiple_files():
    content = load(["examples/playbooks/**/*.md"])
    assert "## HelloWorld" in content
    assert "## FriendlyChat" in content


def test_invalid_path():
    with pytest.raises(FileNotFoundError):
        load(["nonexistent/path.md"])
