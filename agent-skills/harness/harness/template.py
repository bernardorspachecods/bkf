"""Fill a brief template: a text file with {{name}} placeholders that code replaces with values."""
import re
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


class TemplateError(ValueError):
    """A template and its values do not match."""


def render(text, values, source="template"):
    """Replace each {{name}} with values[name] in one pass, so a value is never read as a placeholder.

    A placeholder without a value, or a value no placeholder uses, raises TemplateError: a template
    that drifts from its code fails at once instead of sending an agent a half-filled brief.
    """
    names = set(_PLACEHOLDER.findall(text))
    missing = sorted(names - set(values))
    unused = sorted(set(values) - names)
    if missing:
        raise TemplateError("{0}: no value for {1}".format(source, ", ".join(missing)))
    if unused:
        raise TemplateError("{0}: no placeholder for {1}".format(source, ", ".join(unused)))
    return _PLACEHOLDER.sub(lambda match: str(values[match.group(1)]), text)


def render_file(path, values):
    """Read a template file as written (no newline conversion) and fill it."""
    with open(str(path), "r", encoding="utf-8", newline="") as source:
        text = source.read()
    return render(text, values, source=Path(path).name)
