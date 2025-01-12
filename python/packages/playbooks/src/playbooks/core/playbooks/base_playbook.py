class Playbook:
    @classmethod
    def from_h2(cls, h2):
        """Create a Playbook from an H2 AST node.

        Args:
            h2: Dictionary representing an H2 AST node
        """
        assert h2.get("type") == "h2"

        # Verify no nested h1/h2s
        def check_no_nested_headers(node):
            for child in node.get("children", []):
                if child.get("type") in ["h1", "h2"]:
                    raise Exception("H2 is not expected to have H1s or H2s")
                check_no_nested_headers(child)

        check_no_nested_headers(h2)

        klass = h2.get("text", "").strip()

        # Get description from non-h3 children
        description_parts = []
        h3s = []
        for child in h2.get("children", []):
            if child.get("type") == "h3":
                h3s.append(child)
            else:
                description_parts.append(child.get("text", "").strip())
        description = "\n".join(description_parts).strip()

        if not description:
            description = None

        # Process h3 sections
        trigger = None
        steps = None
        notes = None
        for h3 in h3s:
            h3_title = h3.get("text", "").strip().lower()

            if h3_title == "trigger":
                trigger = h3["markdown"]
            elif h3_title == "steps":
                steps = h3["markdown"]
            elif h3_title == "notes":
                notes = h3["markdown"]

        if steps is None:
            steps = description
            description = None

        playbook = cls(
            klass=klass,
            description=description,
            trigger=trigger,
            steps=steps,
            notes=notes,
            markdown=h2["markdown"],
        )
        return playbook

    def __init__(
        self,
        klass: str,
        description: str,
        trigger: str,
        steps: str,
        notes: str,
        markdown: str,
    ):
        self.klass = klass
        self.description = description
        self.trigger = trigger
        self.steps = steps
        self.notes = notes
        self.markdown = markdown
