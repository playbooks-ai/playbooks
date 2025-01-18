from playbooks.core.playbook import Playbook


def test_playbook_from_h2():
    h2_node = {
        "type": "h2",
        "text": "Sample Class",
        "children": [
            {"type": "h3", "text": "Trigger", "markdown": "Trigger content"},
            {"type": "h3", "text": "Steps", "markdown": "Steps content"},
            {"type": "h3", "text": "Notes", "markdown": "Notes content"},
            {"text": "Description content"},
        ],
        "markdown": "Full markdown content",
    }

    playbook = Playbook.from_h2(h2_node)

    assert playbook.klass == "Sample Class"
    assert playbook.description == "Description content"
    assert playbook.trigger == "Trigger content"
    assert playbook.steps == "Steps content"
    assert playbook.notes == "Notes content"
    assert playbook.markdown == "Full markdown content"


def test_playbook_from_h2_no_description():
    h2_node = {
        "type": "h2",
        "text": "Sample Class",
        "children": [
            {"type": "h3", "text": "Trigger", "markdown": "Trigger content"},
            {"type": "h3", "text": "Steps", "markdown": "Steps content"},
            {"type": "h3", "text": "Notes", "markdown": "Notes content"},
        ],
        "markdown": "Full markdown content",
    }

    playbook = Playbook.from_h2(h2_node)

    assert playbook.klass == "Sample Class"
    assert playbook.description is None
    assert playbook.trigger == "Trigger content"
    assert playbook.steps == "Steps content"
    assert playbook.notes == "Notes content"
    assert playbook.markdown == "Full markdown content"
