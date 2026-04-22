"""Playbook scanner module.

Scans the playbooks directory to generate MCP tool definitions from MD files.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.tsc_logger import get_logger

logger = get_logger()

PLAYBOOKS_DIR = Path(__file__).parent.parent.resolve() / "playbooks"


class PlaybookScanner:
    """Scanner class to generate MCP tool definitions from playbooks."""

    def __init__(self, config=None, playbooks_dir: Path = PLAYBOOKS_DIR):
        self.config = config
        self.playbooks_dir = playbooks_dir
        self.playbooks_dir.mkdir(parents=True, exist_ok=True)

    def scan_playbooks(self) -> List[Dict[str, Any]]:
        """Scan all playbooks and generate tool definitions.

        Returns:
            List[Dict[str, Any]]: List of tool definitions for each playbook.
        """
        tool_definitions = []

        if not self.playbooks_dir.exists():
            logger.warning(f"Playbooks directory not found: {self.playbooks_dir}")
            return tool_definitions

        for playbook_file in sorted(self.playbooks_dir.glob("*.yml")):
            md_file = playbook_file.with_suffix(".md")
            if not md_file.exists():
                logger.warning(
                    f"MD instruction file not found for {playbook_file.name}, skipping"
                )
                continue

            try:
                md_content = md_file.read_text(encoding="utf-8")
                playbook_info = self._parse_md_file(md_content, playbook_file.stem)
                tool_def = self._generate_tool_definition(
                    playbook_file.stem, playbook_info
                )
                tool_definitions.append(tool_def)
            except Exception as e:
                logger.error(f"Failed to process playbook {playbook_file.name}: {e}")

        return tool_definitions

    def _parse_md_file(self, md_content: str, playbook_name: str) -> Dict[str, Any]:
        """Parse MD instruction file.

        Args:
            md_content: Markdown file content.
            playbook_name: Playbook name (without extension).

        Returns:
            Dict[str, Any]: Parsed playbook information.
        """
        info = {
            "name": playbook_name,
            "description": "",
            "parameters": [],
            "use_cases": [],
            "example": "",
            "notes": [],
        }

        sections = re.split(r"^##\s+", md_content, flags=re.MULTILINE)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n")
            title = lines[0].strip()
            content = "\n".join(lines[1:]).strip()

            if title == "Description":
                info["description"] = content
            elif title == "Parameters":
                info["parameters"] = self._parse_parameters(content)
            elif title == "Use Cases":
                info["use_cases"] = [
                    line.strip("- ").strip()
                    for line in content.split("\n")
                    if line.strip().startswith("-")
                ]
            elif title == "Example":
                info["example"] = content
            elif title == "Notes":
                info["notes"] = [
                    line.strip("- ").strip()
                    for line in content.split("\n")
                    if line.strip().startswith("-")
                ]

        return info

    def _parse_parameters(self, content: str) -> List[Dict[str, Any]]:
        """Parse parameters section.

        Args:
            content: Parameters section content.

        Returns:
            List[Dict[str, Any]]: List of parameter definitions.
        """
        params = []
        for line in content.split("\n"):
            line = line.strip()
            if not line.startswith("-"):
                continue

            match = re.match(
                r"-\s+(\w+)\s*\((\w+),\s*(required|optional)\):\s*(.+)", line
            )
            if match:
                params.append(
                    {
                        "name": match.group(1),
                        "type": match.group(2),
                        "required": match.group(3) == "required",
                        "description": match.group(4),
                    }
                )

        return params

    def _generate_tool_definition(
        self, name: str, info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate MCP tool definition.

        Args:
            name: Playbook name.
            info: Parsed playbook information.

        Returns:
            Dict[str, Any]: Tool definition for MCP.
        """
        description = self._build_description(name, info)
        parameters = self._build_parameters(info)

        return {
            "name": f"playbook_{name}",
            "description": description,
            "parameters": parameters,
        }

    def _build_description(self, name: str, info: Dict[str, Any]) -> str:
        """Build tool description for LLM.

        Args:
            name: Playbook name.
            info: Parsed playbook information.

        Returns:
            str: Tool description.
        """
        desc_parts = [
            f"Execute the {name} playbook: {info['description']}",
            "",
            "## Prerequisites",
            "- Target hosts must be configured in inventory.yml first.",
            "- The tool auto-installs Python3 if missing on target hosts.",
            "",
            "## Return Value",
            "Returns execution summary including task_id, status, success_hosts list, and failed_hosts list.",
            "To view failed host details, use get_result(task_id, status='failed').",
        ]

        if info["use_cases"]:
            desc_parts.extend(["", "## Use Cases"])
            for case in info["use_cases"]:
                desc_parts.append(f"- {case}")

        if info["notes"]:
            desc_parts.extend(["", "## Notes"])
            for note in info["notes"]:
                desc_parts.append(f"- {note}")

        if info["example"]:
            desc_parts.extend(["", "## Usage Example", info["example"]])

        return "\n".join(desc_parts)

    def _build_parameters(self, info: Dict[str, Any]) -> Dict[str, Any]:
        """Build parameters schema.

        Args:
            info: Parsed playbook information.

        Returns:
            Dict[str, Any]: Parameters schema.
        """
        properties = {
            "targets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of target hostnames or IPs (required)",
            },
        }
        required_params = ["targets"]

        for param in info["parameters"]:
            param_type = param["type"]
            if param_type == "string":
                properties[param["name"]] = {
                    "type": "string",
                    "description": f"{param['description']} ({'required' if param['required'] else 'optional'})",
                }
            elif param_type == "object":
                properties[param["name"]] = {
                    "type": "object",
                    "description": f"{param['description']} ({'required' if param['required'] else 'optional'})",
                }
            elif param_type == "integer":
                properties[param["name"]] = {
                    "type": "integer",
                    "description": f"{param['description']} ({'required' if param['required'] else 'optional'})",
                }
            elif param_type in ("list", "array"):
                properties[param["name"]] = {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": f"{param['description']} ({'required' if param['required'] else 'optional'})",
                }

            if param["required"]:
                required_params.append(param["name"])

        return {
            "type": "object",
            "properties": properties,
            "required": required_params,
        }


# Global scanner instance
scanner = PlaybookScanner()
