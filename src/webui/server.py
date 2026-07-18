# src/webui/server.py
from __future__ import annotations
import asyncio
import json
import queue
import threading
from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import StreamingResponse, JSONResponse
from starlette.staticfiles import StaticFiles


class WebUISession:
    def __init__(self):
        self.events: list[str] = []
        self._ask_q: queue.Queue = queue.Queue()
        self._ans_q: queue.Queue = queue.Queue()
        self.lock = threading.Lock()

    def push(self, event: str):
        with self.lock:
            self.events.append(event)

    def ask(self, action):
        self._ask_q.put(action)
        return self._ans_q.get()

    def answer(self, decision: bool):
        self._ans_q.put(decision)


def make_app(session: WebUISession) -> Starlette:
    async def sse(request):
        idx = 0
        async def gen():
            nonlocal idx
            while True:
                with session.lock:
                    while idx < len(session.events):
                        yield f"data: {session.events[idx]}\n\n"
                        idx += 1
                await asyncio.sleep(0.2)
        return StreamingResponse(gen(), media_type="text/event-stream")

    async def approve(request):
        data = await request.json()
        session.answer(bool(data.get("approve", False)))
        return JSONResponse({"ok": True})

    async def pending_approval(request):
        try:
            action = session._ask_q.get_nowait()
            return JSONResponse({"pending": True, "action": {"tool": action.tool, "args": action.args}})
        except queue.Empty:
            return JSONResponse({"pending": False})

    routes = [
        Route("/events", sse),
        Route("/approve", approve, methods=["POST"]),
        Route("/pending", pending_approval, methods=["GET"]),
    ]
    app = Starlette(routes=routes)
    static = Path(__file__).parent / "static"
    app.mount("/", StaticFiles(directory=str(static), html=True), name="static")
    return app
