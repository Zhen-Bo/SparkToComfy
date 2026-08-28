"""WebSocket entry point: accept, replay the current state, live until the peer closes."""

import asyncio
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.deps import WsRuntimeDep
from app.runtime import Runtime
from app.ws.schemas import (
    JobQueuedMessage,
    JobStatusMessage,
    ReceiptMessage,
    SystemMessage,
)

router = APIRouter()

MAX_SESSION_ID = 64
BAD_SESSION_CLOSE = 4400
SLOW_CONSUMER_CLOSE = 1011
CLOSE_TIMEOUT = 2


def _valid_session(session_id: str | None) -> bool:
    return bool(session_id) and len(session_id) <= MAX_SESSION_ID


async def _read_forever(websocket: WebSocket) -> None:
    while True:
        await websocket.receive_text()


async def _replay(rt: Runtime, session_id: str, websocket: WebSocket) -> None:
    """Catch a new connection up: engine online or not, any live job, its queue slot."""
    send = rt.hub.send_to_connection
    await send(session_id, websocket, SystemMessage(comfy_online=rt.queue.online))
    for job in rt.registry.for_session(session_id):
        await send(session_id, websocket, ReceiptMessage(prompt_id=job.prompt_id))
        if job.status == "running":
            await send(session_id, websocket, JobStatusMessage(status="running"))
            continue
        slot = rt.queue.slot(job.prompt_id)
        if slot is None:
            continue
        position, eta_seconds = slot
        await send(
            session_id,
            websocket,
            JobQueuedMessage(position=position, eta_seconds=eta_seconds),
        )


async def _close_slow(websocket: WebSocket) -> None:
    """The outbox is already dead and the peer has not noticed. A failed close is fine."""
    with suppress(WebSocketDisconnect, RuntimeError, ConnectionError, TimeoutError):
        await asyncio.wait_for(
            websocket.close(code=SLOW_CONSUMER_CLOSE, reason="slow consumer"),
            timeout=CLOSE_TIMEOUT,
        )


async def _serve(rt: Runtime, session_id: str, websocket: WebSocket) -> None:
    """Read until the peer closes. A dead outbox means this peer cannot keep up, so close it."""
    reader = asyncio.create_task(_read_forever(websocket))
    dead = asyncio.create_task(rt.hub.wait_dead(session_id, websocket))
    try:
        await asyncio.wait({reader, dead}, return_when=asyncio.FIRST_COMPLETED)
        if dead.done() and not reader.done():
            await _close_slow(websocket)
    finally:
        reader.cancel()
        dead.cancel()
        await asyncio.gather(reader, dead, return_exceptions=True)


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    rt: WsRuntimeDep,
    session_id: Annotated[str | None, Query(alias="sessionId")] = None,
):
    if not _valid_session(session_id):
        await websocket.accept()
        await websocket.close(code=BAD_SESSION_CLOSE, reason="invalid session_id")
        return
    assert session_id is not None
    await websocket.accept()
    rt.hub.add_connection(session_id, websocket)
    try:
        await _replay(rt, session_id, websocket)
        await _serve(rt, session_id, websocket)
    finally:
        await rt.hub.remove_connection(session_id, websocket)
