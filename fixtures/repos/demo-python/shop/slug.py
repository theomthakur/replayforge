import re


def slugify(title: str) -> str:
    """Turn a product title into a URL slug: lowercase words joined by single hyphens."""
    lowered = title.lower()
    return re.sub(r"[^a-z0-9]", "-", lowered)
