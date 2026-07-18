# src/harness/tools/base.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class Product:
    exitcode: int
    stdout: str
    stderr: str

class Tool:
    name: str
    def exec(self, args: dict, workdir: str) -> Product: ...