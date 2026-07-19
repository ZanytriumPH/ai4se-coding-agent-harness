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
        self._pending = None  # action awaiting approval — peek-able, NOT consumed by /pending
        self._ans_q: queue.Queue = queue.Queue()
        self.lock = threading.Lock()

    def push(self, event: str):
        with self.lock:
            self.events.append(event)

    def ask(self, action):
        # Park the action as the current pending approval (peek-able via
        # /pending) and block until the browser POSTs /approve. Must NOT use a
        # consumed get_nowait for /pending — otherwise the browser's 1s poll
        # removes the action on the first poll and hides the card on the next,
        # leaving ask() blocked forever with the UI showing nothing.
        with self.lock:
            self._pending = action
        decision = self._ans_q.get()
        with self.lock:
            self._pending = None
        return decision

    def answer(self, decision: bool):
        self._ans_q.put(decision)

    def pending_action(self):
        with self.lock:
            return self._pending


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
        action = session.pending_action()  # peek, does NOT consume
        if action is not None:
            return JSONResponse({"pending": True,
                                 "action": {"tool": action.tool, "args": action.args}})
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


# Module-level app so `uvicorn webui.server:app` works for deploy (G1).
# This serves the frontend + the /events /pending /approve endpoints against a
# fresh session. For a full run (frontend + a driving loop), use
# `harness --run-webui` instead — it serves AND drives an AgentLoop against the
# same session. This bare-uvicorn form is for serving the frontend behind a
# reverse proxy or when the loop is driven by a separate process.
app = make_app(WebUISession())
