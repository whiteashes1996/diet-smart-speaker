"""Local plain-text note tool backend (persistent memory on the Pi).

Stores user notes to a local JSONL file so DeepSeek can recall them later via
tool calls. No cloud, no MCP process required.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from smart_speaker.protocols.tools import ToolSpec

MAX_CONTENT_CHARS = 1000
MAX_SEARCH_RESULTS = 5
MAX_SEARCH_RESULT_CHARS = 1500


class LocalNoteToolBackend:
    """save_note / search_notes / list_notes backed by a local JSONL file."""

    def __init__(self, memory_dir: Path | str = "~/smart-speaker/memory") -> None:
        self._dir = Path(memory_dir).expanduser()
        self._path = self._dir / "notes.jsonl"
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="save_note",
                description=(
                    "把用户明确要记录的信息（偏好、过敏、待办、事实、想法）持久保存到本地。"
                    "当用户说“记住/记下来/提醒我/保存”时使用。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "要保存的完整内容（一两句话）",
                        },
                        "tags": {
                            "type": "string",
                            "description": "可选，逗号分隔的关键词标签",
                        },
                    },
                    "required": ["content"],
                },
            ),
            ToolSpec(
                name="search_notes",
                description=(
                    "在本地已保存的笔记中按关键词检索。"
                    "当用户问“我之前说过/上次/有没有记过/我记过什么”时先调用，"
                    "再用返回的内容回答。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索关键词，多个词用空格分隔",
                        }
                    },
                    "required": ["query"],
                },
            ),
            ToolSpec(
                name="list_notes",
                description="列出最近保存的本地笔记（按时间倒序）。",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "返回条数，默认 10",
                        }
                    },
                },
            ),
        ]

    def _load(self) -> list[dict[str, Any]]:
        if not self._path.is_file():
            return []
        notes: list[dict[str, Any]] = []
        with self._path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    notes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return notes

    def _append(self, note: dict[str, Any]) -> None:
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(note, ensure_ascii=False) + "\n")

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "save_note":
            return self._save_note(arguments)
        if name == "search_notes":
            return self._search_notes(arguments)
        if name == "list_notes":
            return self._list_notes(arguments)
        return json.dumps({"error": f"unknown note tool: {name}"})

    def _save_note(self, arguments: dict[str, Any]) -> str:
        content = str(arguments.get("content", "")).strip()
        if not content:
            return json.dumps({"error": "content is required"})
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS]
        tags = str(arguments.get("tags", "")).strip()
        note = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "content": content,
            "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
        }
        self._append(note)
        return json.dumps({"ok": True, "saved": content}, ensure_ascii=False)

    def _search_notes(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip().lower()
        if not query:
            return json.dumps({"error": "query is required"})
        terms = [t for t in query.split() if t]
        notes = self._load()
        matches: list[dict[str, Any]] = []
        for note in reversed(notes):  # newest first
            haystack = (
                str(note.get("content", "")) + " " + " ".join(note.get("tags", []))
            ).lower()
            if all(term in haystack for term in terms):
                matches.append(note)
                if len(matches) >= MAX_SEARCH_RESULTS:
                    break
        out = {"results": matches, "count": len(matches)}
        text = json.dumps(out, ensure_ascii=False)
        if len(text) > MAX_SEARCH_RESULT_CHARS:
            text = text[:MAX_SEARCH_RESULT_CHARS] + "…"
        return text

    def _list_notes(self, arguments: dict[str, Any]) -> str:
        limit = int(arguments.get("limit", 10) or 10)
        limit = max(1, min(limit, 50))
        notes = self._load()
        recent = list(reversed(notes))[:limit]
        text = json.dumps(
            {"results": recent, "count": len(recent), "total": len(notes)},
            ensure_ascii=False,
        )
        if len(text) > MAX_SEARCH_RESULT_CHARS:
            text = text[:MAX_SEARCH_RESULT_CHARS] + "…"
        return text


class MultiToolBackend:
    """Route tool calls across multiple backends by tool name."""

    def __init__(self, backends: list[Any]) -> None:
        self._route: dict[str, Any] = {}
        self._specs: list[ToolSpec] = []
        for backend in backends:
            for spec in backend.list_tools():
                # First backend to claim a name wins; later duplicates hidden.
                if spec.name in self._route:
                    continue
                self._specs.append(spec)
                self._route[spec.name] = backend

    def list_tools(self) -> list[ToolSpec]:
        return list(self._specs)

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        backend = self._route.get(name)
        if backend is None:
            return json.dumps({"error": f"unknown tool: {name}"})
        return await backend.call(name, arguments)
