import re


def apply_patch(original: str, patch: str) -> str:
    """Apply a unified diff patch to the original text.

    Parameters
    ----------
    original: str
        Original text content.
    patch: str
        Patch in unified diff format without file headers.

    Returns
    -------
    str
        Patched text.
    """
    original_lines = original.splitlines()
    result: list[str] = []
    index = 0
    patch_lines = patch.splitlines()
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    i = 0
    while i < len(patch_lines):
        m = hunk_re.match(patch_lines[i])
        if not m:
            i += 1
            continue
        start_old = int(m.group(1))
        i += 1
        # copy unchanged lines before the hunk
        while index < start_old - 1:
            result.append(original_lines[index])
            index += 1
        while i < len(patch_lines) and not patch_lines[i].startswith("@@"):
            line = patch_lines[i]
            if line.startswith(" "):
                result.append(original_lines[index])
                index += 1
            elif line.startswith("-"):
                index += 1
            elif line.startswith("+"):
                result.append(line[1:])
            i += 1
    result.extend(original_lines[index:])
    return "\n".join(result)
