"""
Tool description loader.

Loads MCP tool descriptions and instructions from Markdown files under
etc/tool_descriptions/. Supports a {{POLLING_RULES}} placeholder that is
automatically replaced with the shared polling rules fragment.
"""

from pathlib import Path
from typing import Optional

from lib.tsc_logger import get_logger

logger = get_logger()

_BASE_DIR = Path(__file__).parent.parent.resolve()
_DESCRIPTIONS_DIR = _BASE_DIR / "etc" / "tool_descriptions"
_INSTRUCTIONS_FILE = _BASE_DIR / "etc" / "instructions.md"
_POLLING_RULES_FILE = _DESCRIPTIONS_DIR / "_polling_rules.md"

# Cache loaded content so files are read only once per process lifetime.
_cache: dict[str, str] = {}


def _read(path: Path) -> str:
    key = str(path)
    if key not in _cache:
        if not path.exists():
            logger.error(f"Description file not found: {path}")
            raise FileNotFoundError(f"Description file not found: {path}")
        _cache[key] = path.read_text(encoding="utf-8")
    return _cache[key]


def _polling_rules() -> str:
    return _read(_POLLING_RULES_FILE)


def load_instructions() -> str:
    """Load global MCP instructions from etc/instructions.md."""
    return _read(_INSTRUCTIONS_FILE)


def load_tool_description(name: str, playbook_prerequisites: bool = False) -> str:
    """Load a tool description from etc/tool_descriptions/<name>.md.

    Replaces the {{POLLING_RULES}} placeholder with the shared polling rules
    fragment before returning.

    Args:
        name: Tool name, e.g. "ansible_shell". The file
              etc/tool_descriptions/<name>.md must exist.
        playbook_prerequisites: If True, load _playbook_prerequisites.md and
              prepend it to the description (used for dynamically registered
              playbook tools).

    Returns:
        Rendered description string ready to pass to @server.mcp.tool().
    """
    description = _read(_DESCRIPTIONS_DIR / f"{name}.md")
    description = description.replace("{{POLLING_RULES}}", _polling_rules())

    if playbook_prerequisites:
        prereq = _read(_DESCRIPTIONS_DIR / "_playbook_prerequisites.md")
        prereq = prereq.replace("{{POLLING_RULES}}", _polling_rules())
        description = prereq + "\n" + description

    return description


def load_playbook_prerequisites() -> str:
    """Load the shared playbook prerequisites block with polling rules resolved."""
    prereq = _read(_DESCRIPTIONS_DIR / "_playbook_prerequisites.md")
    return prereq.replace("{{POLLING_RULES}}", _polling_rules())
