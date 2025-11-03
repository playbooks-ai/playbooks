"""Tests for structured identifier types."""

import pytest

from playbooks.identifiers import AgentID, MeetingID, IDParser


class TestAgentID:
    """Tests for AgentID structured type."""

    def test_parse_spec_format(self):
        """Test parsing agent spec format 'agent 1234'."""
        agent_id = AgentID.parse("agent 1234")
        assert agent_id.id == "1234"
        assert str(agent_id) == "agent 1234"

    def test_parse_raw_id(self):
        """Test parsing raw ID '1234'."""
        agent_id = AgentID.parse("1234")
        assert agent_id.id == "1234"
        assert str(agent_id) == "agent 1234"

    def test_parse_human_alias(self):
        """Test parsing 'human' alias."""
        agent_id = AgentID.parse("human")
        assert agent_id.id == "human"
        assert str(agent_id) == "agent human"

    def test_parse_user_alias(self):
        """Test parsing 'user' alias."""
        agent_id = AgentID.parse("user")
        assert agent_id.id == "human"
        assert str(agent_id) == "agent human"

    def test_parse_case_insensitive_human(self):
        """Test that human aliases are case-insensitive."""
        assert AgentID.parse("HUMAN").id == "human"
        assert AgentID.parse("USER").id == "human"
        assert AgentID.parse("Human").id == "human"

    def test_parse_with_whitespace(self):
        """Test parsing handles leading/trailing whitespace."""
        agent_id = AgentID.parse("  agent 1234  ")
        assert agent_id.id == "1234"

    def test_parse_empty_raises(self):
        """Test that empty spec raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            AgentID.parse("")

    def test_parse_whitespace_only_raises(self):
        """Test parsing whitespace-only string raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            AgentID.parse("   ")

    def test_equality(self):
        """Test AgentID equality based on ID."""
        id1 = AgentID("1234")
        id2 = AgentID("1234")
        id3 = AgentID("5678")

        assert id1 == id2
        assert id1 != id3
        assert id1 != "1234"  # Not equal to strings

    def test_hashable(self):
        """Test AgentID can be used in sets and dicts."""
        id1 = AgentID("1234")
        id2 = AgentID("1234")
        id3 = AgentID("5678")

        # Can be used in set
        agent_set = {id1, id2, id3}
        assert len(agent_set) == 2  # id1 and id2 are equal

        # Can be used as dict key
        agent_dict = {id1: "first", id3: "second"}
        assert agent_dict[id2] == "first"  # id2 equals id1

    def test_immutable(self):
        """Test that AgentID is immutable (frozen dataclass)."""
        agent_id = AgentID("1234")
        with pytest.raises(AttributeError):
            agent_id.id = "5678"

    def test_repr(self):
        """Test developer-friendly repr."""
        agent_id = AgentID("1234")
        assert repr(agent_id) == "AgentID('1234')"


class TestMeetingID:
    """Tests for MeetingID structured type."""

    def test_parse_spec_format(self):
        """Test parsing meeting spec format 'meeting 112'."""
        meeting_id = MeetingID.parse("meeting 112")
        assert meeting_id.id == "112"
        assert str(meeting_id) == "meeting 112"

    def test_parse_raw_id(self):
        """Test parsing raw ID '112'."""
        meeting_id = MeetingID.parse("112")
        assert meeting_id.id == "112"
        assert str(meeting_id) == "meeting 112"

    def test_parse_with_whitespace(self):
        """Test parsing handles leading/trailing whitespace."""
        meeting_id = MeetingID.parse("  meeting 112  ")
        assert meeting_id.id == "112"

    def test_parse_empty_raises(self):
        """Test that empty spec raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MeetingID.parse("")

    def test_parse_whitespace_only_raises(self):
        """Test parsing whitespace-only string raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            MeetingID.parse("   ")

    def test_equality(self):
        """Test MeetingID equality based on ID."""
        id1 = MeetingID("112")
        id2 = MeetingID("112")
        id3 = MeetingID("113")

        assert id1 == id2
        assert id1 != id3
        assert id1 != "112"  # Not equal to strings

    def test_hashable(self):
        """Test MeetingID can be used in sets and dicts."""
        id1 = MeetingID("112")
        id2 = MeetingID("112")
        id3 = MeetingID("113")

        meeting_set = {id1, id2, id3}
        assert len(meeting_set) == 2

        meeting_dict = {id1: "first", id3: "second"}
        assert meeting_dict[id2] == "first"

    def test_immutable(self):
        """Test that MeetingID is immutable."""
        meeting_id = MeetingID("112")
        with pytest.raises(AttributeError):
            meeting_id.id = "113"


class TestIDParser:
    """Tests for IDParser utility."""

    def test_parse_agent_spec(self):
        """Test parsing agent spec returns AgentID."""
        entity_id = IDParser.parse("agent 1234")
        assert isinstance(entity_id, AgentID)
        assert entity_id.id == "1234"

    def test_parse_meeting_spec(self):
        """Test parsing meeting spec returns MeetingID."""
        entity_id = IDParser.parse("meeting 112")
        assert isinstance(entity_id, MeetingID)
        assert entity_id.id == "112"

    def test_parse_human(self):
        """Test parsing 'human' returns AgentID."""
        entity_id = IDParser.parse("human")
        assert isinstance(entity_id, AgentID)
        assert entity_id.id == "human"

    def test_parse_raw_id_defaults_to_agent(self):
        """Test that ambiguous raw IDs default to AgentID."""
        entity_id = IDParser.parse("1234")
        assert isinstance(entity_id, AgentID)
        assert entity_id.id == "1234"

    def test_parse_agent_alias(self):
        """Test parse_agent alias method."""
        agent_id = IDParser.parse_agent("agent 1234")
        assert isinstance(agent_id, AgentID)
        assert agent_id.id == "1234"

    def test_parse_meeting_alias(self):
        """Test parse_meeting alias method."""
        meeting_id = IDParser.parse_meeting("meeting 112")
        assert isinstance(meeting_id, MeetingID)
        assert meeting_id.id == "112"

    def test_parse_empty_raises(self):
        """Test that empty spec raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            IDParser.parse("")


class TestIDComparisons:
    """Tests for ID comparisons and type distinctions."""

    def test_agent_and_meeting_not_equal(self):
        """Test that AgentID and MeetingID are never equal even with same ID."""
        agent_id = AgentID("123")
        meeting_id = MeetingID("123")

        assert agent_id != meeting_id

    def test_string_conversion_roundtrip(self):
        """Test that parsing str(id) returns equivalent ID."""
        original_agent = AgentID("1234")
        roundtrip_agent = AgentID.parse(str(original_agent))
        assert original_agent == roundtrip_agent

        original_meeting = MeetingID("112")
        roundtrip_meeting = MeetingID.parse(str(original_meeting))
        assert original_meeting == roundtrip_meeting
