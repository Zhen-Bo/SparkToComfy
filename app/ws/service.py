"""One outbox per WebSocket: a slow peer fills its own queue without stalling producers."""

import asyncio
import json
from collections import deque
from contextlib import suppress

import structlog
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.models import CustomModel

logger = structlog.stdlib.get_logger(__name__)

MAX_BACKLOG = 256
# Only the newest of these matters: a new one replaces the queued one and does not count against the backlog.
_COALESCE = frozenset({"preview", "progress", "ping"})


def _payload(message: CustomModel) -> tuple[str, str]:
    data = message.model_dump(by_alias=True)
    return str(data.get("type", "")), json.dumps(data)


class _Outbox:
    def __init__(self, hub: "WsHub", session_id: str, conn: WebSocket) -> None:
        self.hub = hub
        self.session_id = session_id
        self.conn = conn
        self.queue: deque[tuple[str, str]] = deque()
        self.events = 0
        self.wake = asyncio.Event()
        self.dead = asyncio.Event()
        self.task = asyncio.create_task(self._pump())

    def put(self, kind: str, text: str) -> None:
        if self.dead.is_set():
            return
        if kind in _COALESCE:
            for index, (queued, _) in enumerate(self.queue):
                if queued == kind:
                    del self.queue[index]
                    break
        elif self.events >= MAX_BACKLOG:
            self._die()
            return
        else:
            self.events += 1
        self.queue.append((kind, text))
        self.wake.set()

    async def _pump(self) -> None:
        try:
            while True:
                while not self.queue:
                    self.wake.clear()
                    await self.wake.wait()
                kind, text = self.queue.popleft()
                if kind not in _COALESCE:
                    self.events -= 1
                await self.conn.send_text(text)
        except (WebSocketDisconnect, RuntimeError, ConnectionError):
            # A peer close raises WebSocketDisconnect; sending after close raises RuntimeError.
            logger.debug("outbox finished", session_id=self.session_id, exc_info=True)
            self._die()

    def _die(self) -> None:
        self.hub.drop(self.session_id, self.conn)
        self.dead.set()
        self.queue.clear()
        self.task.cancel()

    async def aclose(self) -> None:
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task


class WsHub:
    def __init__(self) -> None:
        self.connections: dict[str, dict[WebSocket, _Outbox]] = {}

    def drop(self, session_id: str, conn: WebSocket) -> _Outbox | None:
        group = self.connections.get(session_id)
        if group is None:
            return None
        box = group.pop(conn, None)
        if not group:
            self.connections.pop(session_id, None)
        return box

    def add_connection(self, session_id: str, conn: WebSocket) -> None:
        self.connections.setdefault(session_id, {})[conn] = _Outbox(
            self, session_id, conn
        )

    async def remove_connection(self, session_id: str, conn: WebSocket) -> None:
        box = self.drop(session_id, conn)
        if box is not None:
            await box.aclose()

    async def wait_dead(self, session_id: str, conn: WebSocket) -> None:
        box = self.connections.get(session_id, {}).get(conn)
        if box is None:
            return
        await box.dead.wait()

    async def send_to_connection(
        self, session_id: str, conn: WebSocket, message: CustomModel
    ) -> None:
        box = self.connections.get(session_id, {}).get(conn)
        if box is not None:
            box.put(*_payload(message))

    async def send_to_session(self, session_id: str, message: CustomModel) -> None:
        group = self.connections.get(session_id)
        if not group:
            return
        kind, text = _payload(message)
        for box in list(group.values()):
            box.put(kind, text)

    async def send_to_all(self, message: CustomModel) -> None:
        for session_id in list(self.connections):
            await self.send_to_session(session_id, message)

    async def aclose(self) -> None:
        for group in list(self.connections.values()):
            for box in list(group.values()):
                await box.aclose()
        self.connections.clear()
