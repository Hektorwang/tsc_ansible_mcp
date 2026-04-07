"""
Playbook 扫描器和动态工具生成器

负责扫描 playbooks 目录，解析元数据，生成动态工具定义，并监控文件变化
"""

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from lib.config import Config
from lib.logger import get_logger

logger = get_logger()


class PlaybookScanner:
    """Playbook 扫描器和动态工具生成器"""

    def __init__(self, config: Config):
        self.config = config
        self.playbooks_path = config.playbooks_path
        self.playbooks: Dict[str, Dict[str, Any]] = {}
        self.observer: Optional[Any] = None
        self.update_callback: Optional[Callable[[], None]] = None

    def scan_playbooks(self) -> Dict[str, Dict[str, Any]]:
        """扫描所有 playbook 文件

        Returns:
            字典，键为 playbook 名称（不含扩展名），值为元数据
        """
        if not self.playbooks_path.exists():
            logger.warning(f"playbooks 目录不存在: {self.playbooks_path}")
            return {}

        self.playbooks = {}

        for playbook_file in self.playbooks_path.glob("*.yml"):
            if playbook_file.is_file():
                self._process_playbook_file(playbook_file)

        for playbook_file in self.playbooks_path.glob("*.yaml"):
            if playbook_file.is_file():
                self._process_playbook_file(playbook_file)

        logger.info(f"扫描完成，找到 {len(self.playbooks)} 个有效的 playbook")
        return self.playbooks

    def _process_playbook_file(self, playbook_path: Path) -> None:
        """处理单个 playbook 文件

        Args:
            playbook_path: playbook 文件路径
        """
        playbook_name = playbook_path.stem
        metadata = self.parse_metadata(playbook_path)

        if metadata and metadata.get("description"):
            self.playbooks[playbook_name] = metadata
            logger.info(f"加载 playbook: {playbook_name}")
        else:
            logger.warning(
                f"跳过 playbook '{playbook_name}': 缺少必要的元数据（description 字段）"
            )

    def parse_metadata(self, playbook_path: Path) -> Optional[Dict[str, Any]]:
        """解析 playbook 元数据

        Args:
            playbook_path: playbook 文件路径

        Returns:
            元数据字典，解析失败返回 None
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
            logger.warning(f"解析 playbook 元数据失败: {playbook_path}, 错误: {e}")
            return None

        return metadata

    def _extract_json_metadata(self, content: str) -> Optional[Dict[str, Any]]:
        """从注释中提取 JSON 格式的元数据

        Args:
            content: playbook 文件内容

        Returns:
            元数据字典，解析失败返回 None
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
                    if "default" in param:
                        param["description"] = (
                            f"{param.get('description', '')} (default: {param['default']})"
                        )

            return metadata

        except json.JSONDecodeError as e:
            logger.debug(f"JSON 元数据解析失败: {e}")
            return None
        except Exception as e:
            logger.debug(f"提取 JSON 元数据失败: {e}")
            return None

    def generate_tool_definition(self, metadata: Dict[str, Any]) -> str:
        """生成工具描述

        Args:
            metadata: playbook 元数据

        Returns:
            工具描述字符串
        """
        description_parts = []

        if metadata.get("description"):
            description_parts.append(metadata["description"])

        if metadata.get("parameters"):
            description_parts.append("\n参数说明:")
            for param in metadata["parameters"]:
                param_desc = f"  - {param['name']}"
                if param.get("type"):
                    param_desc += f" ({param['type']})"
                if param.get("description"):
                    param_desc += f": {param['description']}"
                description_parts.append(param_desc)

        if metadata.get("use_cases"):
            description_parts.append("\n使用场景:")
            for use_case in metadata["use_cases"]:
                description_parts.append(f"  - {use_case}")

        if metadata.get("example"):
            description_parts.append("\n示例:")
            example = metadata["example"]
            example_str = json.dumps(example, indent=2, ensure_ascii=False)
            for line in example_str.split("\n"):
                description_parts.append(f"  {line}")

        if metadata.get("notes"):
            description_parts.append("\n注意事项:")
            for note in metadata["notes"]:
                description_parts.append(f"  - {note}")

        return "\n".join(description_parts)

    def start_watching(self, callback: Callable) -> None:
        """启动文件监控

        Args:
            callback: 文件变化时的回调函数
        """
        if self.observer is not None:
            logger.warning("文件监控已在运行")
            return

        self.update_callback = callback

        event_handler = PlaybookEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.playbooks_path), recursive=False)
        self.observer.start()

        logger.info(f"开始监控 playbook 目录: {self.playbooks_path}")

    def stop_watching(self) -> None:
        """停止文件监控"""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("停止监控 playbook 目录")

    def on_file_created(self, file_path: Path) -> None:
        """文件创建事件处理

        Args:
            file_path: 创建的文件路径
        """
        if file_path.suffix not in [".yml", ".yaml"]:
            return

        logger.info(f"检测到新 playbook 文件: {file_path}")
        self._process_playbook_file(file_path)

        if self.update_callback:
            self.update_callback()

    def on_file_modified(self, file_path: Path) -> None:
        """文件修改事件处理

        Args:
            file_path: 修改的文件路径
        """
        if file_path.suffix not in [".yml", ".yaml"]:
            return

        logger.info(f"检测到 playbook 文件修改: {file_path}")

        playbook_name = file_path.stem
        if playbook_name in self.playbooks:
            del self.playbooks[playbook_name]

        self._process_playbook_file(file_path)

        if self.update_callback:
            self.update_callback()

    def on_file_deleted(self, file_path: Path) -> None:
        """文件删除事件处理

        Args:
            file_path: 删除的文件路径
        """
        if file_path.suffix not in [".yml", ".yaml"]:
            return

        logger.info(f"检测到 playbook 文件删除: {file_path}")

        playbook_name = file_path.stem
        if playbook_name in self.playbooks:
            del self.playbooks[playbook_name]
            logger.info(f"已移除 playbook: {playbook_name}")

        if self.update_callback:
            self.update_callback()


class PlaybookEventHandler(FileSystemEventHandler):
    """Playbook 文件事件处理器"""

    def __init__(self, scanner: PlaybookScanner):
        self.scanner = scanner

    def on_created(self, event):
        """文件创建事件"""
        if not event.is_directory:
            self.scanner.on_file_created(Path(event.src_path))

    def on_modified(self, event):
        """文件修改事件"""
        if not event.is_directory:
            self.scanner.on_file_modified(Path(event.src_path))

    def on_deleted(self, event):
        """文件删除事件"""
        if not event.is_directory:
            self.scanner.on_file_deleted(Path(event.src_path))
