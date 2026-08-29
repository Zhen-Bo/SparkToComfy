"""End-to-end checks against a real ComfyUI.

These really generate images, so the whole module carries the `e2e` marker and
`addopts = "-m 'not e2e'"` skips it by default. Run it with `uv run pytest -m e2e`.
The module skips itself when ComfyUI is unreachable.

Everything runs in-process:
* HTTP goes through the httpx ASGITransport, whose `client=` argument sets the source IP.
* WebSocket goes through AsgiWs in conftest, because ASGITransport has no WebSocket support.
* No real server means nobody runs lifespan, so the module opens it once (`_lifespan`).

The checks depend on each other in time: an image must exist before history, the image
proxy or a soft delete can be checked. Module-scoped fixtures carry those dependencies,
so running any single test on its own still sets its prerequisites up.
"""

import asyncio
import socket
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from conftest import EXAMPLE_VALUES, AsgiWs, assert_camel
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import runtime
from app.comfy import client as comfy_client
from app.database import JobRow
from app.main import api, app

pytestmark = [pytest.mark.e2e, pytest.mark.asyncio(loop_scope="module")]


def _comfy_reachable() -> bool:
    parsed = urlparse(comfy_client.COMFY_URL)
    try:
        with socket.create_connection((parsed.hostname, parsed.port or 80), timeout=1):
            return True
    except OSError:
        return False


if not _comfy_reachable():
    pytest.skip(
        f"needs a real ComfyUI running at {comfy_client.COMFY_URL}",
        allow_module_level=True,
    )


SESSION = "e2e-check-f4-a"
SESSION_B = "e2e-check-f4-b"
IP2 = "127.0.0.2"
# The one set of valid values lives in conftest.
# Only the two fields that must change are overridden here.
PARAMS = {**EXAMPLE_VALUES, "positive": "a red apple on a table", "seed": -1}


def body_of(params=None, session_id=SESSION):
    return {
        "workflowId": "example",
        "sessionId": session_id,
        "params": PARAMS if params is None else params,
    }


# --- environment ---


async def wait_comfy_online(timeout=20):
    """Wait for ComfyUI by watching the system broadcast on the WebSocket, not by polling a flag."""
    ws = AsgiWs("e2e-boot-watch")
    await ws.open()
    try:
        while True:
            m = await ws.wait_for_type("system", timeout=timeout)
            if m["comfyOnline"]:
                return
    finally:
        await ws.close()


@pytest_asyncio.fixture(scope="module", loop_scope="module", autouse=True)
async def _lifespan(tmp_path_factory):
    """One lifespan for the whole module: one real ComfyUI connection, one temp database."""
    db_path = tmp_path_factory.mktemp("e2e") / "e2e.db"
    with mock.patch.object(runtime, "default_db_path", return_value=db_path):
        async with app.router.lifespan_context(app):
            await wait_comfy_online()
            yield


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def api2():
    """A second source IP, used to check that one IP can only hold one job in flight."""
    transport = ASGITransport(app=app, client=(IP2, 12345))
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


# --- helpers ---


async def get_json(client, path):
    resp = await client.get(path)
    return resp.status_code, resp.json()


async def post_json(client, path, body):
    resp = await client.post(path, json=body)
    return resp.status_code, (resp.json() if resp.content else {})


async def delete_status(client, path):
    resp = await client.delete(path)
    return resp.status_code


async def fetch_bytes(client, path):
    resp = await client.get(path)
    return resp.status_code, resp.headers, resp.content


async def fetch_status(client, path):
    resp = await client.get(path)
    return resp.status_code


async def db_rows(prompt_id):
    async with api.state.runtime.db.session() as session:
        result = await session.execute(
            select(JobRow.status).where(JobRow.prompt_id == prompt_id)
        )
    return result.all()


@asynccontextmanager
async def open_ws(session_id):
    ws = AsgiWs(session_id)
    await ws.open()
    try:
        yield ws
    finally:
        await ws.close()


async def recv_json(ws, timeout):
    m, _ = await ws.recv(timeout=timeout)
    assert_camel(m, "ws")
    return m


async def expect_system(ws, where):
    m = await recv_json(ws, 5)
    assert set(m) == {"type", "comfyOnline"}, (where, m)
    assert m["type"] == "system", (where, m)
    assert m["comfyOnline"] is True, (where, m)


async def wait_receipt(ws, timeout=15):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remain = deadline - loop.time()
        assert remain > 0, f"no receipt within {timeout}s"
        m = await recv_json(ws, remain)
        if m.get("type") != "receipt":
            continue
        assert set(m) == {"type", "promptId"}, m
        assert m["promptId"], m
        return m["promptId"]


# The exact key set of every job message, by status.
JOB_KEYS = {
    "queued": {"type", "status", "position", "etaSeconds"},
    "running": {"type", "status"},
    "cancelled": {"type", "status"},
    "done": {"type", "status", "images"},
    "error": {"type", "status", "code"},
}


def assert_job_shape(m):
    assert m["status"] in JOB_KEYS, m
    assert set(m) == JOB_KEYS[m["status"]], m
    if m["status"] == "queued":
        assert isinstance(m["position"], int) and m["position"] >= 1, m
        assert m["etaSeconds"] is None or m["etaSeconds"] >= 0, m


async def wait_status(ws, status, timeout):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remain = deadline - loop.time()
        assert remain > 0, f"no {status} within {timeout}s"
        m = await recv_json(ws, remain)
        if m.get("type") != "job":
            continue
        assert_job_shape(m)
        assert m["status"] != "error", m
        if m["status"] == status:
            return m


async def wait_done(ws, timeout):
    seq = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remain = deadline - loop.time()
        assert remain > 0, f"no done within {timeout}s, only saw {seq}"
        m = await recv_json(ws, remain)
        mark = m["type"]
        if mark == "preview":
            assert set(m) == {"type", "mime", "data"}, m
            continue
        if mark == "progress":
            assert set(m) == {"type", "value", "max"}, m
        if mark == "job":
            assert_job_shape(m)
            mark = m["status"]
        if mark not in seq:
            seq.append(mark)
        if mark == "done":
            return m, seq


# --- producing fixtures: the ordering dependencies live here, not in test order ---


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def first_run(api_client):
    """Accept, in-flight, done and one more image, all on a single WebSocket connection.

    Splitting these apart would leave nothing in flight to check, so the actions stay together and each assertion becomes its own test.
    """
    async with open_ws(SESSION) as ws:
        await expect_system(ws, "connect-1")
        accepted = await post_json(api_client, "/v1/generate", body_of())
        pid = await wait_receipt(ws)
        second = await post_json(api_client, "/v1/generate", body_of())
        inflight = await get_json(api_client, f"/v1/history?sessionId={SESSION}")
        done, seq = await wait_done(ws, 180)
        fast = await post_json(
            api_client, "/v1/generate", body_of({**PARAMS, "steps": 1})
        )
        third = await wait_receipt(ws)
        await wait_done(ws, 120)
    return SimpleNamespace(
        pid=pid,
        third=third,
        done=done,
        seq=seq,
        accepted=accepted,
        second=second,
        inflight=inflight,
        fast=fast,
    )


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def history_row(api_client, first_run):
    status, rows = await get_json(api_client, f"/v1/history?sessionId={SESSION}")
    assert status == 200, status
    assert_camel(rows, "history")
    return next(r for r in rows if r["promptId"] == first_run.pid)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def image_url(history_row):
    return history_row["images"][0]


async def submit_then_cancel(client, ws, body, canceller):
    """Submit, take the receipt, cancel, wait for the terminal message.

    Cancelling a queued job and resubmitting after a cancel both run through this.
    """
    accepted = await post_json(client, "/v1/generate", body)
    pid = await wait_receipt(ws)
    cancelled = await post_json(
        canceller, f"/v1/jobs/{pid}/cancel", {"sessionId": body["sessionId"]}
    )
    msg = await wait_status(ws, "cancelled", 15)
    return SimpleNamespace(pid=pid, accepted=accepted, cancelled=cancelled, msg=msg)


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def cancels(api_client, api2):
    """One pair of WebSockets and one slow running job `a`, shared by every cancel check."""
    slow = body_of({**PARAMS, "steps": 50})
    slow_b = body_of({**PARAMS, "steps": 50}, session_id=SESSION_B)
    async with open_ws(SESSION) as ws, open_ws(SESSION_B) as wsb:
        await expect_system(ws, "connect-a")
        await expect_system(wsb, "connect-b")

        started = await post_json(api_client, "/v1/generate", slow)
        a = await wait_receipt(ws)
        await wait_status(ws, "running", 120)

        queued = await submit_then_cancel(api2, wsb, slow_b, api_client)
        again = await submit_then_cancel(api2, wsb, slow_b, api_client)

        cancel_a = await post_json(
            api_client, f"/v1/jobs/{a}/cancel", {"sessionId": SESSION}
        )
        msg_a = await wait_status(ws, "cancelled", 15)
        rows_a, rows_b = await db_rows(a), await db_rows(queued.pid)
    return SimpleNamespace(
        a=a,
        queued=queued,
        again=again,
        started=started,
        cancel_a=cancel_a,
        msg_a=msg_a,
        rows_a=rows_a,
        rows_b=rows_b,
    )


# --- generate, rate limit, in flight ---


async def test_generate_is_accepted(first_run):
    assert first_run.accepted == (200, {"promptId": first_run.pid}), first_run.accepted
    assert first_run.fast == (200, {"promptId": first_run.third}), first_run.fast


async def test_second_generate_from_the_same_ip_is_rejected(first_run):
    status, body = first_run.second
    assert status == 429, (status, body)
    assert body["code"] == "job_active", body
    assert_camel(body, "job-active")


async def test_inflight_job_is_not_in_history(first_run):
    status, rows = first_run.inflight
    assert status == 200, status
    assert_camel(rows, "history-inflight")
    assert all(r["promptId"] != first_run.pid for r in rows), (
        "an in-flight job must not reach the DB"
    )


async def test_generate_reaches_done(first_run):
    assert first_run.seq[-3:] == ["running", "progress", "done"], first_run.seq
    assert first_run.done["images"] == [f"/v1/images/{first_run.pid}?index=0"], (
        first_run.done
    )


# --- history ---


async def test_history_row_shape(history_row):
    assert set(history_row) == {
        "workflowId",
        "promptId",
        "params",
        "images",
        "createdAt",
        "finishedAt",
    }, history_row


async def test_history_row_content(history_row, first_run):
    created = datetime.fromisoformat(history_row["createdAt"])
    finished = datetime.fromisoformat(history_row["finishedAt"])
    assert created < finished, history_row
    assert history_row["params"]["seed"].isdigit(), (
        "seed must be stored as the resolved value"
    )
    assert history_row["images"] == first_run.done["images"], history_row
    assert history_row["images"] == [f"/v1/images/{first_run.pid}?index=0"], history_row


# --- image proxy ---


async def test_image_proxy(api_client, first_run, image_url):
    status, headers, body = await fetch_bytes(api_client, image_url)
    assert status == 200, status
    assert body[:4] == b"\x89PNG", body[:16]
    disp = headers.get("content-disposition", "")
    assert disp.startswith("inline; filename=") and disp.endswith('.png"'), disp
    assert await fetch_status(api_client, f"/v1/images/{first_run.pid}?index=9") == 404


# --- soft delete ---


async def test_softdelete(api_client, first_run, image_url):
    both = f"promptId={first_run.pid}&promptId={first_run.third}"
    mixed = f"{both}&promptId={uuid.uuid4()}"
    cases = [
        (f"/v1/history?sessionId=other&{both}", 404, "another session must not delete"),
        (f"/v1/history?sessionId={SESSION}&{both}", 204, "first delete"),
        (
            f"/v1/history?sessionId={SESSION}&{both}",
            204,
            "a repeat delete is still 204",
        ),
        (
            f"/v1/history?sessionId={SESSION}&{mixed}",
            404,
            "an unknown promptId cancels the batch",
        ),
    ]
    for path, expected, why in cases:
        assert await delete_status(api_client, path) == expected, why
    _, rows = await get_json(api_client, f"/v1/history?sessionId={SESSION}")
    gone = (first_run.pid, first_run.third)
    assert all(r["promptId"] not in gone for r in rows), rows
    assert await fetch_status(api_client, image_url) == 404, (
        "the image proxy must 404 after a soft delete"
    )


# --- lora cover ---


async def test_lora_cover(api_client):
    status, headers, body = await fetch_bytes(
        api_client, "/v1/lora/cover?lora=R9FG018QZ03G8N8C4JKMMKCJA0"
    )
    ctype = headers.get("content-type", "")
    assert status == 200 and ctype.startswith("image/"), (status, ctype)
    assert len(body) > 1000


# --- cancel: queued, ip release, running ---


async def test_cancel_queued_job(cancels):
    assert cancels.started == (200, {"promptId": cancels.a}), cancels.started
    assert cancels.queued.accepted == (200, {"promptId": cancels.queued.pid}), (
        cancels.queued.accepted
    )
    assert cancels.queued.cancelled == (204, {}), cancels.queued.cancelled
    assert set(cancels.queued.msg) == {"type", "status"}, cancels.queued.msg
    assert cancels.rows_b == [], "a cancelled job must leave no DB row"


async def test_cancel_releases_the_ip(cancels):
    assert cancels.again.accepted == (200, {"promptId": cancels.again.pid}), (
        "cancelling must release the IP",
        cancels.again.accepted,
    )
    assert cancels.again.cancelled == (204, {}), cancels.again.cancelled


async def test_cancel_running_job(cancels):
    assert cancels.cancel_a == (204, {}), cancels.cancel_a
    assert set(cancels.msg_a) == {"type", "status"}, cancels.msg_a
    assert cancels.rows_a == [], (
        "a cancelled job must leave no DB row, error rows included"
    )


# --- cancel a finished job ---


async def test_cancelled_jobs_never_reach_history(api_client, cancels):
    _, rows = await get_json(api_client, f"/v1/history?sessionId={SESSION}")
    assert all(r["promptId"] != cancels.a for r in rows), rows
    _, rows_b = await get_json(api_client, f"/v1/history?sessionId={SESSION_B}")
    gone = (cancels.queued.pid, cancels.again.pid)
    assert all(r["promptId"] not in gone for r in rows_b), rows_b


async def test_cancel_of_a_finished_job(api_client, first_run, cancels):
    done = await post_json(
        api_client, f"/v1/jobs/{first_run.pid}/cancel", {"sessionId": SESSION}
    )
    assert done == (204, {}), ("cancelling a finished job counts as success", done)
    status, body = await post_json(
        api_client, f"/v1/jobs/{cancels.a}/cancel", {"sessionId": SESSION}
    )
    assert (status, body["code"]) == (404, "not_found"), (
        "re-cancelling a cancelled job is 404",
        body,
    )
    status, body = await post_json(
        api_client, f"/v1/jobs/{first_run.pid}/cancel", {"sessionId": "other"}
    )
    assert (status, body["code"]) == (404, "not_found"), (
        "another session's job is 404",
        body,
    )
