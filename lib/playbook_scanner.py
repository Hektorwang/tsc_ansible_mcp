"""
Playbook scanner and dynamic tool generator.

Scans playbooks directory, parses metadata, generates dynamic tool definitions.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.config import Config
from lib.tsc_logger import get_logger

logger = get_logger()


class PlaybookScanner:
    """Playbook scanner and dynamic tool generator."""

    def __init__(self, config: Config):
        self.config = config
        self.playbooks_path = config.playbooks_path
        self.playbooks: Dict[str, Dict[str, Any]] = {}

    def scan_playbooks(self) -> Dict[str, Dict[str, Any]]:
        """Scan all playbook files.

        Returns:
            Dictionary with playbook name (without extension) as key and metadata as value.
        """
        if not self.playbooks_path.exists():
            logger.warning(f"Playbooks directory does not exist: {self.playbooks_path}")
            return {}

        self.playbooks = {}

        for playbook_file in self.playbooks_path.glob("*.yml"):
            if playbook_file.is_file():
                self._process_playbook_file(playbook_file)

        for playbook_file in self.playbooks_path.glob("*.yaml"):
            if playbook_file.is_file():
                self._process_playbook_file(playbook_file)

        logger.info(f"Scan completed, found {len(self.playbooks)} valid playbooks")
        return self.playbooks

    def _process_playbook_file(self, playbook_path: Path) -> None:
        """Process a single playbook file.

        Args:
            playbook_path: Playbook file path.
        """
        playbook_name = playbook_path.stem
        tool_name = f"playbook_{playbook_name}"
        metadata = self.parse_metadata(playbook_path)

        if metadata and metadata.get("description"):
            metadata["tool_name"] = tool_name
            self.playbooks[playbook_name] = metadata
            logger.info(f"Loaded playbook: {playbook_name} -> Tool name: {tool_name}")
        else:
            logger.warning(
                f"Skipped playbook '{playbook_name}': Missing required metadata (description field)"
            )

    def parse_metadata(self, playbook_path: Path) -> Optional[Dict[str, Any]]:
        """Parse playbook metadata.

        Args:
            playbook_path: Playbook file path.

        Returns:
            Metadata dictionary, None if parsing failed.
        """
        metadata: Dict[str, Any] = {
            "name": playbook_path.stem,
            "path": str(playbook_path),
            "description": "",
            "author": "",
            "version": "",
            "tags": [],
            "parameters": [],
        }

        try:
            content = playbook_path.read_text(encoding="utf-8")

            json_metadata = self._extract_json_metadata(content)
            if json_metadata:
                metadata.update(json_metadata)
                metadata["name"] = playbook_path.stem
                metadata["path"] = str(playbook_path)
                return metadata

            in_description = False
            description_lines = []

            for line in content.split("\n"):
                stripped = line.strip()

                if stripped.startswith("---"):
                    break

                if not stripped.startswith("#"):
                    continue

                comment = stripped[1:].strip()

                if comment.startswith("@description:"):
                    metadata["description"] = comment.split(":", 1)[1].strip()
                elif comment.startswith("Description:"):
                    in_description = True
                    desc_content = comment.split(":", 1)[1].strip()
                    if desc_content:
                        description_lines.append(desc_content)
                elif in_description:
                    if comment and not comment.startswith(
                        (
                            "Author:",
                            "Version:",
                            "Tags:",
                            "Parameters:",
                            "Use Cases:",
                            "Example:",
                            "Notes:",
                            "Playbook:",
                        )
                    ):
                        description_lines.append(comment)
                    else:
                        in_description = False
                        if description_lines:
                            metadata["description"] = " ".join(description_lines)

                if comment.startswith("@author:"):
                    metadata["author"] = comment.split(":", 1)[1].strip()
                elif comment.startswith("Author:"):
                    metadata["author"] = comment.split(":", 1)[1].strip()

                if comment.startswith("@version:"):
                    metadata["version"] = comment.split(":", 1)[1].strip()
                elif comment.startswith("Version:"):
                    metadata["version"] = comment.split(":", 1)[1].strip()

                if comment.startswith("@tags:"):
                    tags_str = comment.split(":", 1)[1].strip()
                    metadata["tags"] = [
                        t.strip() for t in tags_str.split(",") if t.strip()
                    ]
                elif comment.startswith("Tags:"):
                    tags_str = comment.split(":", 1)[1].strip()
                    metadata["tags"] = [
                        t.strip() for t in tags_str.split(",") if t.strip()
                    ]

                if comment.startswith("@parameters:"):
                    pass
                elif comment.startswith("Parameters:"):
                    pass
                else:
                    param_line = comment.lstrip("-").strip()
                    if param_line and "(" in param_line and ":" in param_line:
                        param_match = re.match(r"(\w+)\s*\((\w+)\):\s*(.+)", param_line)
                        if param_match:
                            metadata["parameters"].append(
                                {
                                    "name": param_match.group(1),
                                    "type": param_match.group(2),
                                    "description": param_match.group(3),
                                }
                            )
                    elif param_line and ":" in param_line:
                        parts = param_line.split(":", 1)
                        if len(parts) == 2:
                            param_name = parts[0].strip()
                            param_desc = parts[1].strip()
                            if param_name and not param_name.startswith(
                                (
                                    "Use",
                                    "Example",
                                    "Notes",
                                    "Playbook",
                                    "Description",
                                    "Author",
                                    "Version",
                                    "Tags",
                                )
                            ):
                                metadata["parameters"].append(
                                    {
                                        "name": param_name,
                                        "description": param_desc,
                                    }
                                )

            if description_lines and not metadata["description"]:
                metadata["description"] = " ".join(description_lines)

        except Exception as e:
            logger.warning(f"Failed to parse playbook metadata: {playbook_path}, error: {e}")
            return None

        return metadata

    def _extract_json_metadata(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON format metadata from comments.

        Args:
            content: Playbook file content.

        Returns:
            Metadata dictionary, None if parsing failed.
        """
        try:
            json_lines = []
            in_meta = False

            for line in content.split("\n"):
                stripped = line.strip()

                if stripped.startswith("# @meta:"):
                    in_meta = True
                    json_start = stripped[8:].strip()
                    if json_start:
                        json_lines.append(json_start)
                    continue

                if in_meta:
                    if stripped.startswith("#"):
                        json_line = stripped[1:].strip()
                        json_lines.append(json_line)
                    elif stripped.startswith("---"):
                        break

            if not json_lines:
                return None

            json_str = "\n".join(json_lines)
            metadata = json.loads(json_str)

            if "parameters" in metadata:
                for param in metadata["parameters"]:
                    if param.get("required") is False:
                        param["description"] = (
                            f"{param.get('description', '')} [optional]"
                        )
                    elif param.get("required") is True:
                        param["description"] = (
                            f"{param.get('description', '')} [required]"
                        )

            return metadata

        except json.JSONDecodeError as e:
            logger.debug(f"JSON metadata parsing failed: {e}")
            return None
        except Exception as e:
            logger.debug(f"Failed to extract JSON metadata: {e}")
            return None

    def generate_tool_definition(self, metadata: Dict[str, Any]) -> str:
        """Generate tool description.

        Args:
            metadata: Playbook metadata.

        Returns:
            Tool description string.
        """
        description_parts = []

        if metadata.get("description"):
            description_parts.append(metadata["description"])

        if metadata.get("parameters"):
            description_parts.append("Parameters Instruction:")
            for param in metadata["parameters"]:
                param_desc = f"  - {param['name']}"
                if param.get("type"):
                    param_desc += f" ({param['type']})"
                if param.get("description"):
                    param_desc += f": {param['description']}"
                description_parts.append(param_desc)

        if metadata.get("use_cases"):
            description_parts.append("Use Cases:")
            for use_case in metadata["use_cases"]:
                description_parts.append(f"  - {use_case}")

        if metadata.get("example"):
            description_parts.append("Example:")
            example = metadata["example"]
            example_str = json.dumps(example, indent=2, ensure_ascii=False)
            for line in example_str.split("\n"):
                description_parts.append(f"  {line}")

        if metadata.get("notes"):
            description_parts.append("Notes:")
            for note in metadata["notes"]:
                description_parts.append(f"  - {note}")

        return "\n".join(description_parts)
