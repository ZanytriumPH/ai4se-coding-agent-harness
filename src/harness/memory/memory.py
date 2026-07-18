from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from harness.models import MemoryEntry


@dataclass
class RecallQuery:
    tags: set[str]


class Memory:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def store(self, entry: MemoryEntry) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": entry.id, "tags": entry.tags,
                "content": entry.content, "created_at": entry.created_at,
            }, ensure_ascii=False) + "\n")

    def _load_all(self) -> list[MemoryEntry]:
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            out.append(MemoryEntry(
                id=d["id"], tags=d["tags"], content=d["content"], created_at=d["created_at"],
            ))
        return out

    def recall(self, query: RecallQuery) -> list[MemoryEntry]:
        return [e for e in self._load_all() if query.tags.issubset(set(e.tags))]