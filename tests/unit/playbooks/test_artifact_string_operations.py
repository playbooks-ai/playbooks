"""Tests for Artifact string operations support."""

from playbooks.state.variables import Artifact


def test_artifact_len():
    """Test len(artifact) returns content length."""
    artifact = Artifact(name="test", summary="Test", value="Hello World")
    assert len(artifact) == 11


def test_artifact_len_with_non_string_content():
    """Test len(artifact) with non-string content (converts to string first)."""
    artifact = Artifact(name="test", summary="Test", value={"key": "value"})
    # Should convert dict to string first, then get length
    assert len(artifact) == len(str({"key": "value"}))


def test_artifact_add():
    """Test artifact + 'text' concatenation."""
    artifact = Artifact(name="test", summary="Test", value="Hello")
    result = artifact + " World"
    assert result == "Hello World"
    assert isinstance(result, str)


def test_artifact_radd():
    """Test 'text' + artifact concatenation."""
    artifact = Artifact(name="test", summary="Test", value="World")
    result = "Hello " + artifact
    assert result == "Hello World"
    assert isinstance(result, str)


def test_artifact_add_with_non_string():
    """Test artifact + number (converts to string)."""
    artifact = Artifact(name="test", summary="Test", value="Value: ")
    result = artifact + 42
    assert result == "Value: 42"


def test_artifact_mul():
    """Test artifact * n multiplication."""
    artifact = Artifact(name="test", summary="Test", value="Ha")
    result = artifact * 3
    assert result == "HaHaHa"
    assert isinstance(result, str)


def test_artifact_rmul():
    """Test n * artifact multiplication."""
    artifact = Artifact(name="test", summary="Test", value="Ha")
    result = 3 * artifact
    assert result == "HaHaHa"
    assert isinstance(result, str)


def test_artifact_getitem_index():
    """Test artifact[index] indexing."""
    artifact = Artifact(name="test", summary="Test", value="Hello")
    assert artifact[0] == "H"
    assert artifact[1] == "e"
    assert artifact[-1] == "o"


def test_artifact_getitem_slice():
    """Test artifact[start:end] slicing."""
    artifact = Artifact(name="test", summary="Test", value="Hello World")
    assert artifact[0:5] == "Hello"
    assert artifact[6:] == "World"
    assert artifact[:5] == "Hello"
    assert artifact[::2] == "HloWrd"


def test_artifact_contains():
    """Test 'substring' in artifact."""
    artifact = Artifact(name="test", summary="Test", value="Hello World")
    assert "Hello" in artifact
    assert "World" in artifact
    assert "lo Wo" in artifact
    assert "xyz" not in artifact


def test_artifact_eq_with_string():
    """Test artifact == 'string'."""
    artifact = Artifact(name="test", summary="Test", value="Hello")
    assert artifact == "Hello"
    assert not (artifact == "World")


def test_artifact_eq_with_artifact():
    """Test artifact == artifact."""
    artifact1 = Artifact(name="test1", summary="Test 1", value="Hello")
    artifact2 = Artifact(name="test2", summary="Test 2", value="Hello")
    artifact3 = Artifact(name="test3", summary="Test 3", value="World")

    assert artifact1 == artifact2  # Same content
    assert not (artifact1 == artifact3)  # Different content


def test_artifact_lt():
    """Test artifact < 'string'."""
    artifact = Artifact(name="test", summary="Test", value="apple")
    assert artifact < "banana"
    assert not (artifact < "aardvark")


def test_artifact_lt_with_artifact():
    """Test artifact < artifact."""
    artifact1 = Artifact(name="test1", summary="Test 1", value="apple")
    artifact2 = Artifact(name="test2", summary="Test 2", value="banana")

    assert artifact1 < artifact2
    assert not (artifact2 < artifact1)


def test_artifact_le():
    """Test artifact <= 'string'."""
    artifact = Artifact(name="test", summary="Test", value="apple")
    assert artifact <= "banana"
    assert artifact <= "apple"
    assert not (artifact <= "aardvark")


def test_artifact_gt():
    """Test artifact > 'string'."""
    artifact = Artifact(name="test", summary="Test", value="banana")
    assert artifact > "apple"
    assert not (artifact > "cherry")


def test_artifact_ge():
    """Test artifact >= 'string'."""
    artifact = Artifact(name="test", summary="Test", value="banana")
    assert artifact >= "apple"
    assert artifact >= "banana"
    assert not (artifact >= "cherry")


def test_artifact_str_with_dict_content():
    """Test str(artifact) with dict content."""
    content = {"key": "value", "number": 42}
    artifact = Artifact(name="test", summary="Test", value=content)

    # str() should convert the dict to string
    result = str(artifact)
    assert isinstance(result, str)
    assert "key" in result
    assert "value" in result


def test_artifact_str_with_list_content():
    """Test str(artifact) with list content."""
    content = [1, 2, 3, "four"]
    artifact = Artifact(name="test", summary="Test", value=content)

    # str() should convert the list to string
    result = str(artifact)
    assert isinstance(result, str)
    assert "[1, 2, 3, 'four']" == result


def test_artifact_string_operations_with_dict_content():
    """Test that string operations work with non-string content."""
    artifact = Artifact(name="test", summary="Test", value={"a": 1})

    # All operations should work by converting to string first
    assert len(artifact) > 0
    assert "a" in artifact
    result = artifact + " more text"
    assert isinstance(result, str)


def test_artifact_concatenation_chain():
    """Test chaining multiple concatenations."""
    artifact = Artifact(name="test", summary="Test", value="middle")
    result = "start " + artifact + " end"
    assert result == "start middle end"


def test_artifact_in_format_string():
    """Test artifact used in f-string-like contexts."""
    artifact = Artifact(name="test", summary="Test", value="World")
    # This simulates what happens in string formatting
    result = "Hello " + artifact
    assert result == "Hello World"


def test_artifact_slice_operations():
    """Test various slice operations."""
    artifact = Artifact(name="test", summary="Test", value="0123456789")

    assert artifact[2:5] == "234"
    assert artifact[5:] == "56789"
    assert artifact[:5] == "01234"
    assert artifact[-3:] == "789"
    assert artifact[:-3] == "0123456"
    assert artifact[::2] == "02468"
    assert artifact[1::2] == "13579"
    assert artifact[::-1] == "9876543210"


def test_artifact_comparison_edge_cases():
    """Test comparison edge cases."""
    artifact = Artifact(name="test", summary="Test", value="test")

    # Compare with empty string
    assert artifact > ""
    assert artifact >= ""
    assert not (artifact < "")

    # Compare with itself
    assert artifact == artifact
    assert artifact <= artifact
    assert artifact >= artifact
