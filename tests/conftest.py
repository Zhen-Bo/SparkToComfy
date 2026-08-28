"""Shared test environment and helpers.

Every test gets its own Runtime (its own temp database, registry, hub and eta model), so nothing global needs clearing and any test can run on its own.

The schema comes from the real alembic migration: it runs once per session into a template file and every test copies that file.
"""

import asyncio
import json
import os
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# app.config builds its settings at import time and the shipped default keeps the API docs closed.
# The docs tests assert where the docs live once open, so open them before the app package loads.
os.environ.setdefault("SERVER__DOCS", "true")

from app import runtime
from app.database import Database
from app.main import api, app
from app.settings import ROOT

# config/workflow.yaml is git-ignored, so it holds whatever workflows the machine happens to deploy.
# The tests assert against the shipped example, which is the only registry every checkout has.
EXAMPLE_REGISTRY = ROOT / "config" / "workflow.example.yaml"


@pytest.fixture(scope="session")
def example_registry():
    return EXAMPLE_REGISTRY


# --- valid parameters ---

# One valid set of values for the example workflow.
# e2e reuses it with only the prompt and seed changed, so it is never written out a second time.
EXAMPLE_VALUES = {
    "model": "krea2Turbo_v10_fp8.safetensors",
    "quality": "",
    "positive": "a cat",
    "negative": "",
    "size": {"preset": "square", "highres": False, "landscape": False},
    "steps": 8,
    "cfg": 1,
    "seed": 42,
    "sampler": "euler",
    "scheduler": "beta",
    "upscale": 1,
    "lora": [],
}


@pytest.fixture
def example_values():
    return deepcopy(EXAMPLE_VALUES)


# --- environment ---


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory):
    """Migrate once. Each test copies this file and gets the real migrated schema."""
    template = tmp_path_factory.mktemp("schema") / "template.db"
    asyncio.run(_migrate(template))
    return template


async def _migrate(path: Path) -> None:
    db = Database(path)
    await db.migrate()
    await db.aclose()


@pytest.fixture
def db_path(migrated_db, tmp_path):
    fresh = tmp_path / "test.db"
    shutil.copy(migrated_db, fresh)
    return fresh


@pytest_asyncio.fixture
async def rt(db_path):
    """One Runtime per test, and it is the one the app serves this request from."""
    value = await runtime.build(db_path=db_path, registry=EXAMPLE_REGISTRY)
    api.state.runtime = value
    yield value
    api.state.runtime = None
    await value.aclose()


@pytest_asyncio.fixture
async def client(rt):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


# --- helpers ---

_DATA_KEYS = {"options", "basic", "advanced", "presets"}


def assert_camel(obj, where="$", keys_are_data=False):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "params":
                continue
            if not keys_are_data:
                assert "_" not in k, f"{where}.{k}"
            assert_camel(v, f"{where}.{k}", keys_are_data=k in _DATA_KEYS)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            assert_camel(v, f"{where}[{i}]", keys_are_data=keys_are_data)


class AsgiWs:
    """Call the app the way uvicorn does: a websocket scope plus receive/send, no socket."""

    def __init__(self, session_id):
        self.incoming = asyncio.Queue()
        self.outgoing = asyncio.Queue()
        query = b"" if session_id is None else f"sessionId={session_id}".encode()
        self.scope = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": "ws",
            "path": "/v1/ws",
            "raw_path": b"/v1/ws",
            "query_string": query,
            "root_path": "",
            "headers": [(b"host", b"127.0.0.1:8000")],
            "client": ("127.0.0.1", 51000),
            "server": ("127.0.0.1", 8000),
            "subprotocols": [],
            "state": {},
        }
        self.task = None

    async def send(self, message):
        await self.outgoing.put(message)

    async def open(self):
        await self.incoming.put({"type": "websocket.connect"})
        self.task = asyncio.create_task(app(self.scope, self.incoming.get, self.send))
        first = await asyncio.wait_for(self.outgoing.get(), timeout=5)
        assert first["type"] == "websocket.accept", first

    async def recv(self, timeout: float = 5):
        m = await asyncio.wait_for(self.outgoing.get(), timeout=timeout)
        assert m["type"] == "websocket.send", m
        return json.loads(m["text"]), m["text"]

    async def drain(self, timeout=0.3):
        out = []
        while True:
            try:
                out.append(await self.recv(timeout=timeout))
            except TimeoutError:
                return out

    async def wait_for_type(self, kind, timeout=10):
        """Wait for a message of the given type. Event driven: it wakes on arrival, never polls."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remain = deadline - loop.time()
            assert remain > 0, f"no {kind} within {timeout}s"
            m, _ = await self.recv(timeout=remain)
            if m.get("type") == kind:
                return m

    async def close(self):
        assert self.task is not None
        await self.incoming.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self.task, timeout=5)
