"""Async and fake-server checks: WebSocket handshake, offline, ASGI, slow consumers.

Every test takes its own Runtime (the `rt` fixture in conftest), so nothing global needs clearing and execution order does not matter.
Every wait is event driven; none of them sleep on a fixed poll interval.
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager, suppress
from types import SimpleNamespace
from typing import NamedTuple
from unittest import mock

import pytest
import pytest_asyncio
import structlog
import websockets
from conftest import AsgiWs, assert_camel
from fastapi import HTTPException
from sqlalchemy import select

from app.comfy import client as comfy_client
from app.database import JobRow, JobSubmission, now
from app.jobs.models import Job
from app.jobs.router import generate
from app.jobs.schemas import GenerateRequest
from app.ws import service as ws_service
from app.ws.schemas import (
    JobQueuedMessage,
    PreviewMessage,
    ProgressMessage,
    ReceiptMessage,
)

# --- helpers ---


def make_job(prompt_id, session_id, ip, params):
    return Job(
        submission=JobSubmission(
            prompt_id=prompt_id,
            session_id=session_id,
            workflow_id="example",
            params={**params, "seed": "42"},
            created_at=now(),
        ),
        ip=ip,
        size_key=("example", 1536 * 1536),
        dims=(1536, 1536),
        upscale=1,
    )


class RecordingConn:
    """Fake WebSocket connection that only records the JSON sent to it.

    When gated, nothing goes out until the gate opens.
    """

    def __init__(self, gated=False):
        self.received = []
        self.gate = asyncio.Event()
        self.arrived = asyncio.Event()
        if not gated:
            self.gate.set()

    async def send_text(self, text):
        await self.gate.wait()
        self.received.append(json.loads(text))
        self.arrived.set()

    async def wait_for(self, count, timeout=10, what="messages"):
        """Wait until count messages arrive. Wakes on arrival, never polls on an interval."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while len(self.received) < count:
            self.arrived.clear()
            remain = deadline - loop.time()
            short = f"only {len(self.received)}/{count} {what} within {timeout}s"
            assert remain > 0, short
            try:
                await asyncio.wait_for(self.arrived.wait(), timeout=remain)
            except TimeoutError:
                raise AssertionError(short) from None
        return self.received


async def fake_comfy(port):
    async def handler(conn):
        async for _ in conn:
            pass

    return await websockets.serve(handler, "127.0.0.1", port)


@asynccontextmanager
async def comfy_link(rt):
    """Run an in-process fake ComfyUI WebSocket server, point the runtime at it and listen."""
    server = await fake_comfy(0)
    port = server.sockets[0].getsockname()[1]
    stub = comfy_client.ComfyClient(f"http://127.0.0.1:{port}")
    original, rt.ctx.comfy = rt.ctx.comfy, stub
    task = asyncio.create_task(stub.listen(rt.events.handle))
    try:
        yield server
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await stub.aclose()
        server.close()
        await server.wait_closed()
        rt.ctx.comfy = original


@asynccontextmanager
async def watching(rt, session_id):
    """Attach a connection used only to watch broadcasts, so online and offline waits never poll a flag."""
    conn = RecordingConn()
    rt.hub.add_connection(session_id, conn)
    try:
        yield conn
    finally:
        await rt.hub.remove_connection(session_id, conn)


@pytest_asyncio.fixture
async def comfy_online(rt):
    """Flip the online flag through the real path, then tear down, leaving an environment that never hits the queue in the background."""
    async with watching(rt, "comfy-online-watch") as watcher:
        async with comfy_link(rt):
            await watcher.wait_for(1, what="online broadcasts")
        assert watcher.received == [{"type": "system", "comfyOnline": True}], (
            watcher.received
        )
    assert rt.queue.online, "the online flag must survive"


# --- websocket handshake ---


async def test_ws_without_session_id_is_closed_4400(rt):
    ws = AsgiWs(None)
    await ws.open()
    closed = await asyncio.wait_for(ws.outgoing.get(), timeout=5)
    assert closed["type"] == "websocket.close", "a missing session_id must close(4400)"
    assert closed["code"] == 4400, closed
    assert closed["reason"] == "invalid session_id", closed
    await ws.close()


async def test_ws_first_message_is_system(rt):
    ws = AsgiWs(uuid.uuid4().hex)
    await ws.open()
    try:
        msg, _ = await ws.recv()
        assert set(msg) == {"type", "comfyOnline"}, msg
        assert msg["type"] == "system", msg
        assert isinstance(msg["comfyOnline"], bool), msg
        assert_camel(msg, "system")
    finally:
        await ws.close()


# --- engine offline ---

OFF_SESSION = "s-off"
OFF_IP = "127.0.0.9"


async def test_offline_detection_fails_running_jobs(rt, example_values):
    conn = RecordingConn()
    pid = "offline-" + uuid.uuid4().hex
    async with watching(rt, "offline-watch") as watcher:
        async with comfy_link(rt) as server:
            await watcher.wait_for(1, what="online broadcasts")

            rt.hub.add_connection(OFF_SESSION, conn)
            assert rt.registry.reserve_ip(OFF_IP, pid) is None
            rt.registry.add_job(make_job(pid, OFF_SESSION, OFF_IP, example_values))

            await rt.hub.send_to_session(
                OFF_SESSION, JobQueuedMessage(position=1, eta_seconds=None)
            )
            await conn.wait_for(1, what="queued messages")
            assert conn.received[-1] == {
                "type": "job",
                "status": "queued",
                "position": 1,
                "etaSeconds": None,
            }, conn.received[-1]

            server.close()
            await server.wait_closed()
            await conn.wait_for(3, what="offline messages")

    assert not rt.queue.online, "the flag did not turn offline"
    assert rt.registry.for_session(OFF_SESSION) == ()
    probe_id = "probe-" + uuid.uuid4().hex
    assert rt.registry.reserve_ip(OFF_IP, probe_id) is None, (
        "going offline must release the IP"
    )
    rt.registry.release_ip(OFF_IP, probe_id)
    assert conn.received[-2] == {
        "type": "job",
        "status": "error",
        "code": "comfyui_offline",
    }, conn.received
    assert conn.received[-1] == {"type": "system", "comfyOnline": False}, conn.received

    async with rt.db.session() as session:
        result = await session.execute(
            select(JobRow.status, JobRow.error).where(JobRow.prompt_id == pid)
        )
        rows = result.all()
    assert rows == [("error", "comfyui_offline")], rows


class Blocked(NamedTuple):
    workflow_id: str
    overrides: dict
    status: int
    detail: str


@pytest.mark.parametrize(
    "case",
    [
        Blocked("nope", {}, 404, "not_found"),
        Blocked("example", {"steps": 999}, 400, "bad_request"),
        Blocked("example", {}, 502, "comfyui_unreachable"),
    ],
    ids=["unknown-workflow", "param-out-of-range", "engine-offline"],
)
async def test_generate_is_blocked_while_offline(rt, example_values, case):
    body = GenerateRequest.model_validate(
        {
            "workflow_id": case.workflow_id,
            "session_id": OFF_SESSION,
            "params": {**example_values, **case.overrides},
        },
        by_name=True,
    )
    request = SimpleNamespace(client=SimpleNamespace(host=OFF_IP))
    with pytest.raises(HTTPException) as err:  # generate must be blocked while offline
        await generate(body, request, rt)  # pyright: ignore[reportArgumentType]
    assert (err.value.status_code, err.value.detail) == (case.status, case.detail), (
        err.value
    )


REJECTION = {
    "error": {"type": "prompt_outputs_failed_validation", "message": "x"},
    "node_errors": {
        "6": {
            "errors": [
                {
                    "type": "value_not_in_list",
                    "extra_info": {"received_value": "SECRET_PROMPT_TEXT"},
                }
            ]
        }
    },
}


async def test_comfyui_rejection_keeps_the_prompt_out_of_the_warning(
    rt, comfy_online, example_values, caplog
):
    caplog.set_level(logging.DEBUG)
    body = GenerateRequest.model_validate(
        {
            "workflow_id": "example",
            "session_id": OFF_SESSION,
            "params": example_values,
        },
        by_name=True,
    )
    request = SimpleNamespace(client=SimpleNamespace(host=OFF_IP))
    reject = mock.patch.object(
        rt.comfy, "submit_prompt", side_effect=comfy_client.ComfyError(REJECTION)
    )
    with reject, pytest.raises(HTTPException) as err:
        await generate(body, request, rt)  # pyright: ignore[reportArgumentType]
    assert (err.value.status_code, err.value.detail) == (400, "bad_request"), err.value
    # The reason is bound to the log context, so the exception handler's WARNING line carries it.
    reason = structlog.contextvars.get_contextvars()["reason"]
    assert "prompt_outputs_failed_validation" in reason, reason
    assert "SECRET_PROMPT_TEXT" not in reason, reason
    debug = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert any("SECRET_PROMPT_TEXT" in m for m in debug), debug


async def test_reconnect_brings_comfy_back_online(rt):
    conn = RecordingConn()
    rt.hub.add_connection(OFF_SESSION, conn)
    async with comfy_link(rt):
        await conn.wait_for(1, what="online messages")
    assert conn.received == [{"type": "system", "comfyOnline": True}], conn.received


class Terminal(NamedTuple):
    kind: str
    extra: dict
    code: str


@pytest.mark.parametrize(
    "case",
    [
        Terminal("execution_error", {"exception_message": "boom"}, "execution_failed"),
        Terminal("execution_interrupted", {}, "interrupted"),
    ],
    ids=["execution-error", "interrupted"],
)
async def test_job_event_releases_the_job(rt, example_values, case):
    conn = RecordingConn()
    rt.hub.add_connection(OFF_SESSION, conn)
    pid = f"event-{case.kind}-{uuid.uuid4().hex}"
    assert rt.registry.reserve_ip(OFF_IP, pid) is None, pid
    rt.registry.add_job(make_job(pid, OFF_SESSION, OFF_IP, example_values))
    await rt.events.handle(case.kind, {"prompt_id": pid, **case.extra})
    assert rt.registry.get(pid) is None, case.kind
    await conn.wait_for(1, what=f"{case.kind} messages")
    assert conn.received[-1]["code"] == case.code, (case.kind, conn.received[-1])
    assert rt.registry.reserve_ip(OFF_IP, f"after-{case.kind}") is None, (
        "the IP must be released"
    )


# --- ASGI connections ---

ASGI_SESSION = "asgi-queued"
ASGI_PID = "asgi-" + uuid.uuid4().hex
ASGI_IP = "127.0.0.13"
BCAST_SESSION = "asgi-bcast"
ASGI_QUEUE = {
    "queue_running": [[0, "foreign-running"]],
    "queue_pending": [[1, "foreign-pending"], [2, ASGI_PID]],
}


async def test_asgi_connections_never_poll_the_queue(rt, comfy_online, example_values):
    conns = []
    try:
        assert rt.registry.reserve_ip(ASGI_IP, ASGI_PID) is None
        rt.registry.add_job(make_job(ASGI_PID, ASGI_SESSION, ASGI_IP, example_values))
        with mock.patch.object(
            rt.comfy, "get_queue", mock.AsyncMock(return_value=ASGI_QUEUE)
        ):
            await rt.events.refresh_positions()
        assert rt.queue.slot(ASGI_PID) == (2, None), rt.queue.slot(ASGI_PID)

        counter = mock.AsyncMock(return_value=ASGI_QUEUE)
        with mock.patch.object(rt.comfy, "get_queue", counter):
            for i in range(19):
                idle = AsgiWs(f"asgi-idle-{i}")
                await idle.open()
                conns.append(idle)
            queued = AsgiWs(ASGI_SESSION)
            await queued.open()
            conns.append(queued)
            initial = [m for m, _ in await queued.drain()]
            assert counter.await_count == 0, (
                "a new connection must not hit the ComfyUI queue"
            )
            assert initial == [
                {"type": "system", "comfyOnline": True},
                {"type": "receipt", "promptId": ASGI_PID},
                {"type": "job", "status": "queued", "position": 2, "etaSeconds": None},
            ], initial
    finally:
        for conn in conns:
            await conn.close()
        rt.registry.remove(ASGI_PID)


async def test_asgi_same_session_gets_the_same_payload(rt, comfy_online):
    conns = []
    counter = mock.AsyncMock(return_value=ASGI_QUEUE)
    try:
        with mock.patch.object(rt.comfy, "get_queue", counter):
            b1, b2 = AsgiWs(BCAST_SESSION), AsgiWs(BCAST_SESSION)
            await b1.open()
            await b2.open()
            conns += [b1, b2]
            for label, conn in (("b1", b1), ("b2", b2)):
                only = await conn.drain()
                assert len(only) == 1, (label, only)
                assert only[0][0] == {"type": "system", "comfyOnline": True}, (
                    label,
                    only,
                )
            await rt.hub.send_to_session(
                BCAST_SESSION, JobQueuedMessage(position=7, eta_seconds=42)
            )
            g1, raw1 = await b1.recv()
            g2, raw2 = await b2.recv()
            expected = {
                "type": "job",
                "status": "queued",
                "position": 7,
                "etaSeconds": 42,
            }
            assert g1 == expected, g1
            assert g2 == expected, g2
            assert raw1 == raw2, (
                "two connections of one session must get byte-identical JSON"
            )
            assert counter.await_count == 0, (
                "a broadcast must not hit the ComfyUI queue"
            )
    finally:
        for conn in conns:
            await conn.close()


# --- slow consumers ---

SLOW_A = "slow-return"
SLOW_B = "slow-coalesce"
SLOW_C = "slow-backlog"


class JammedWs(AsgiWs):
    """Accept succeeds, then the connection stops accepting anything after the first message."""

    def __init__(self, session_id):
        super().__init__(session_id)
        self.handed = 0
        self.jam = asyncio.Event()

    async def send(self, message):
        if message["type"] == "websocket.send":
            self.handed += 1
            await self.jam.wait()
        await self.outgoing.put(message)


def _flood_index(m):
    if m["type"] == "job":
        return m["position"]
    if m["type"] == "progress":
        return m["value"]
    return int(m["data"])


def _close_frames(ws):
    frames = []
    while not ws.outgoing.empty():
        m = ws.outgoing.get_nowait()
        if m["type"] == "websocket.close":
            frames.append(m)
    return frames


async def test_slow_consumer_does_not_block_the_producer(rt):
    stuck = RecordingConn(gated=True)
    rt.hub.add_connection(SLOW_A, stuck)
    try:
        await asyncio.wait_for(
            rt.hub.send_to_session(SLOW_A, ReceiptMessage(prompt_id="stuck-1")),
            timeout=2,
        )
    except TimeoutError as err:
        raise AssertionError(
            "the producer stalled: send_to_session never returned"
        ) from err
    assert stuck.received == [], stuck.received

    live = RecordingConn()
    rt.hub.add_connection(SLOW_A, live)
    for i in range(1, 6):
        await asyncio.wait_for(
            rt.hub.send_to_session(SLOW_A, ReceiptMessage(prompt_id=f"m{i}")), timeout=2
        )
    await live.wait_for(5, what="messages on the healthy connection")
    assert [m["promptId"] for m in live.received] == [f"m{i}" for i in range(1, 6)], (
        live.received
    )
    assert stuck.received == [], "the stuck connection must receive nothing"
    await rt.hub.remove_connection(SLOW_A, stuck)
    await rt.hub.remove_connection(SLOW_A, live)


async def test_slow_consumer_coalesces_frames(rt):
    slow = RecordingConn(gated=True)
    rt.hub.add_connection(SLOW_B, slow)
    flood = [
        JobQueuedMessage(position=1, eta_seconds=None),
        PreviewMessage(mime="image/jpeg", data="2"),
        ProgressMessage(value=3, max=100),
        PreviewMessage(mime="image/jpeg", data="4"),
        JobQueuedMessage(position=5, eta_seconds=None),
        ProgressMessage(value=6, max=100),
        PreviewMessage(mime="image/jpeg", data="7"),
        JobQueuedMessage(position=8, eta_seconds=None),
    ]
    for message in flood:
        await asyncio.wait_for(rt.hub.send_to_session(SLOW_B, message), timeout=2)
    slow.gate.set()
    await slow.wait_for(5, what="messages after the drain")
    for _ in range(20):
        await asyncio.sleep(0)
    order = [(m["type"], _flood_index(m)) for m in slow.received]
    assert order == [
        ("job", 1),
        ("job", 5),
        ("progress", 6),
        ("preview", 7),
        ("job", 8),
    ], order
    indexes = [i for _, i in order]
    assert indexes == sorted(indexes), (
        "indexes must increase; a stale frame must not follow a later job"
    )
    await rt.hub.remove_connection(SLOW_B, slow)


async def test_backlog_overflow_closes_only_the_jammed_connection(rt, comfy_online):
    jammed, healthy = JammedWs(SLOW_C), AsgiWs(SLOW_C)
    await jammed.open()
    await healthy.open()
    limit = ws_service.MAX_BACKLOG
    for i in range(limit + 1):
        await rt.hub.send_to_session(SLOW_C, ReceiptMessage(prompt_id=f"f{i}"))
        await asyncio.sleep(0)
    assert jammed.task is not None
    await asyncio.wait_for(jammed.task, timeout=5)

    assert jammed.handed == 1, (
        "a connection that never reads must jam on the first message"
    )
    closes = _close_frames(jammed)
    assert closes and closes[0]["code"] == 1011, closes
    group = rt.hub.connections[SLOW_C]
    assert len(group) == 1, "only the overflowing connection may be dropped"

    got = [m for m, _ in await healthy.drain()]
    assert got[0] == {"type": "system", "comfyOnline": True}, got[0]
    assert [m["promptId"] for m in got[1:]] == [f"f{i}" for i in range(limit + 1)], len(
        got
    )

    box = next(iter(group.values()))
    await healthy.close()
    assert SLOW_C not in rt.hub.connections, rt.hub.connections
    assert box.task.done(), box.task
