def simple_shorten(text, width, placeholder="..."):
    if len(text) <= width:
        return text
    return text[: width - len(placeholder)] + placeholder
