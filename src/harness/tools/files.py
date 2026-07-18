# src/harness/tools/files.py
from __future__ import annotations
from pathlib import Path
from .base import Tool, Product

def _safe(workdir: str, path: str) -> Path:
    base = Path(workdir).resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"path escape detected: {path}")
    return target

class ReadFileTool(Tool):
    name = "read_file"
    def exec(self, args, workdir):
        try:
            txt = _safe(workdir, args["path"]).read_text(encoding="utf-8")
            return Product(0, txt, "")
        except Exception as e:
            return Product(1, "", str(e))

class WriteFileTool(Tool):
    name = "write_file"
    def exec(self, args, workdir):
        try:
            t = _safe(workdir, args["path"])
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(args["content"], encoding="utf-8")
            return Product(0, f"wrote {args['path']}", "")
        except Exception as e:
            return Product(1, "", str(e))